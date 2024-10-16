# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther
from pyramid.view import view_config
from sqlalchemy.exc import NoResultFound

from warehouse.malware.models import MalwareCheck, MalwareCheckState, MalwareCheckType
from warehouse.malware.tasks import backfill, remove_verdicts, run_scheduled_check

EVALUATION_RUN_SIZE = 10000


@view_config(
    route_name="admin.checks.list",
    renderer="admin/malware/checks/index.html",
    permission="moderator",
    request_method="GET",
    uses_session=True,
)
def get_checks(request):
    all_checks = request.db.query(MalwareCheck)
    active_checks = []
    for check in all_checks:
        if not check.is_stale:
            active_checks.append(check)

    active_checks.sort(key=lambda check: check.created, reverse=True)

    return {"checks": active_checks}


@view_config(
    route_name="admin.checks.detail",
    renderer="admin/malware/checks/detail.html",
    permission="moderator",
    request_method="GET",
    uses_session=True,
)
def get_check(request):
    check = get_check_by_name(request.db, request.matchdict["check_name"])

    all_checks = (
        request.db.query(MalwareCheck)
        .filter(MalwareCheck.name == request.matchdict["check_name"])
        .order_by(MalwareCheck.version.desc())
        .all()
    )

    return {
        "check": check,
        "checks": all_checks,
        "states": MalwareCheckState,
        "evaluation_run_size": EVALUATION_RUN_SIZE,
    }


@view_config(
    route_name="admin.checks.run_evaluation",
    permission="admin",
    request_method="POST",
    uses_session=True,
    require_methods=False,
    require_csrf=True,
)
def run_evaluation(request):
    check = get_check_by_name(request.db, request.matchdict["check_name"])

    if check.state not in (MalwareCheckState.Enabled, MalwareCheckState.Evaluation):
        request.session.flash(
            "Check must be in 'enabled' or 'evaluation' state to manually execute.",
            queue="error",
        )
        return HTTPSeeOther(
            request.route_path("admin.checks.detail", check_name=check.name)
        )

    if check.check_type == MalwareCheckType.EventHook:
        request.session.flash(
            f"Running {check.name} on {EVALUATION_RUN_SIZE} {check.hooked_object.value}s\
!",
            queue="success",
        )
        request.task(backfill).delay(check.name, EVALUATION_RUN_SIZE)

    else:
        request.session.flash(f"Running {check.name} now!", queue="success")
        request.task(run_scheduled_check).delay(check.name, manually_triggered=True)

    return HTTPSeeOther(
        request.route_path("admin.checks.detail", check_name=check.name)
    )


@view_config(
    route_name="admin.checks.change_state",
    permission="admin",
    request_method="POST",
    uses_session=True,
    require_methods=False,
    require_csrf=True,
)
def change_check_state(request):
    check = get_check_by_name(request.db, request.matchdict["check_name"])

    try:
        check_state = request.POST["check_state"]
    except KeyError:
        raise HTTPNotFound

    try:
        check.state = MalwareCheckState(check_state)
    except ValueError:
        request.session.flash("Invalid check state provided.", queue="error")
    else:
        if check.state == MalwareCheckState.WipedOut:
            request.task(remove_verdicts).delay(check.name)
        request.session.flash(
            f"Changed {check.name!r} check to {check.state.value!r}!", queue="success"
        )
    finally:
        return HTTPSeeOther(
            request.route_path("admin.checks.detail", check_name=check.name)
        )


def get_check_by_name(db, check_name):
    try:
        # Throw an exception if and only if no results are returned.
        newest = (
            db.query(MalwareCheck)
            .filter(MalwareCheck.name == check_name)
            .order_by(MalwareCheck.version.desc())
            .limit(1)
            .one()
        )
    except NoResultFound:
        raise HTTPNotFound

    return newest
