from app.policy.models import PolicyDecision
from app.policy.rules import POLICY_RULES


class PolicyEngine:

    def evaluate(
        self,
        category: str,
        classifier_action: str,
    ) -> PolicyDecision:

        rule = POLICY_RULES.get(
            category,
            POLICY_RULES["UNKNOWN"],
        )

        if (
            classifier_action == "DO_NOT_HEAL"
            and rule.allowed
        ):
            return PolicyDecision(
                category=category,
                risk_level="HIGH",
                allowed=False,
                action="DO_NOT_HEAL",
                max_attempts=0,
                requires_approval=True,
                reason=(
                    "Classifier marked this failure as "
                    "unsafe for automatic healing."
                ),
            )

        return PolicyDecision(
            category=rule.category,
            risk_level=rule.risk_level,
            allowed=rule.allowed,
            action=rule.action,
            max_attempts=rule.max_attempts,
            requires_approval=rule.requires_approval,
            reason=rule.reason,
        )