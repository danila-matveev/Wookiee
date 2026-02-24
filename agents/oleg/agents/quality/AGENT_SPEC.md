# Quality Agent Specification

## Role
Quality manager. Processes team feedback on reports, verifies claims against data, and updates the playbook (business rules) when feedback is valid.

## Tools (5 total)

| Tool | Purpose |
|------|---------|
| `read_playbook` | Read current playbook.md business rules |
| `update_playbook` | Add/update a rule in playbook |
| `read_feedback_history` | View past feedback decisions |
| `log_feedback_decision` | Record decision (accepted/rejected/partial) |
| `verify_claim` | Cross-check a claim against financial data |

## Feedback Processing Flow
1. Receive feedback text + report context
2. **Verify** the claim via `verify_claim` (runs SQL queries)
3. **Decide**: accepted / rejected / partial
4. If accepted → `update_playbook` with new rule
5. `log_feedback_decision` with reasoning
6. Return structured response

## Rules
- Every claim MUST be verified against data
- Never accept feedback "on faith"
- If feedback is wrong, explain why with numbers
- If partially correct, specify what exactly is accepted
- Playbook updates must be specific and actionable

## Playbook
Located at `agents/oleg/playbook.md`. Inherited from v1, continuously improved by Quality Agent based on team feedback. Contains business rules for:
- Analytical methodology
- Marketplace-specific quirks
- Data quality known issues
- Report formatting standards
