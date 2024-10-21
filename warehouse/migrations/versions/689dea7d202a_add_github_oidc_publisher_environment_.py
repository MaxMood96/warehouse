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
"""
add GitHub OIDC publisher environment constraint

Revision ID: 689dea7d202a
Revises: d142f435bb39
Create Date: 2023-04-11 17:57:08.941312
"""

import sqlalchemy as sa

from alembic import op

revision = "689dea7d202a"
down_revision = "d142f435bb39"


def upgrade():
    op.add_column(
        "github_oidc_publishers", sa.Column("environment", sa.String(), nullable=True)
    )
    op.add_column(
        "pending_github_oidc_publishers",
        sa.Column("environment", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_column("pending_github_oidc_publishers", "environment")
    op.drop_column("github_oidc_publishers", "environment")
