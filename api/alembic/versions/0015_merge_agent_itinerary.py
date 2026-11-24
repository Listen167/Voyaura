"""Join the independently merged agent and formal itinerary migration branches."""

revision = "0015_merge_agent_itinerary"
down_revision = ("0014_agent_workflows", "0014_itinerary_contracts")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
