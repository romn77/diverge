# Diverge Workbench Domain

Diverge Workbench is an internal research and decision-support workspace for market analysis, screening, portfolio context, and trading journal workflows. This context captures the business language used to distinguish planned trades, executed trades, and post-trade review.

## Language

**Trade Plan**:
A pre-trade intent that defines the conditions, thesis, trigger, risk boundary, and expected management rules before any execution occurs.
_Avoid_: trade record draft, pending trade record, loose trade idea

**Trade Plan Status**:
The lifecycle state of a trade plan: `planned` before execution, `executed` after it becomes a trade record, or `expired` when it ends without execution.
_Avoid_: draft, ready, triggered, cancelled

**Trade Plan Status Reason**:
A system-generated explanation for why a trade plan reached its current status.
_Avoid_: cancellation reason, user-written expiry reason

**Trade Plan Expiry**:
The required cutoff time after which a trade plan is no longer valid if it has not produced a trade record.
_Avoid_: planned horizon, holding period

**Trade Record**:
A factual record of an executed trade, including entry facts and, when available, exit facts.
_Avoid_: trade plan, review

**Execution Note**:
A note on the trade record that captures real-time execution context or deviations without changing the originating plan baseline.
_Avoid_: plan correction, revised baseline

**Trade Plan Snapshot**:
The copy of a trade plan's key terms captured on the trade record at the moment the plan is executed.
_Avoid_: live plan lookup, latest plan state

**Analysis Reference**:
A link from a plan, record, or review back to the analysis snapshot that informed it.
_Avoid_: copied report content, required evidence

**Execution Baseline**:
The plan terms used to judge whether an executed trade followed its originating trade plan.
_Avoid_: editable plan fields, latest plan terms

**Planned Entry**:
The pre-trade entry condition or entry zone that defines when a trade plan may be executed.
_Avoid_: executed entry price, fill price

**Reward Target**:
The required profit-taking or reward rule for a trade plan, expressed as a price, zone, R-multiple, staged exit, or condition.
_Avoid_: optional upside note

**Risk Rule**:
The required loss-control rule for a trade plan, expressed as a stop price, invalidation condition, technical condition, or other executable risk boundary.
_Avoid_: vague caution note

**Position Plan**:
The required sizing rule for a trade plan, expressed in a quantifiable form such as shares, notional amount, portfolio percentage, risk budget, or staged sizing rule.
_Avoid_: light position, depends, discretionary size

**Trade Review**:
A post-decision assessment that evaluates a trade record and, when a trade plan exists, compares the actual execution against that plan.
_Avoid_: trade record, feedback

**Plan Execution Assessment**:
The review dimension that judges whether a trade followed its trade plan, or flags that no plan existed.
_Avoid_: optional plan note

**Journal**:
The workspace area that holds trade plans, executed trade records, and trade reviews.
_Avoid_: separate plans module

**Plan Source**:
The origin of a trade plan, such as manual creation or an analysis-prefilled form.
_Avoid_: plan status, evidence quality

## Relationships

- A **Trade Plan** may produce zero or one **Trade Records**.
- A **Trade Record** may reference at most one originating **Trade Plan**.
- A **Trade Review** belongs to exactly one **Trade Record**.
- A **Trade Review** evaluates the linked **Trade Plan** when the **Trade Record** has one.
- A **Trade Record** may exist without an originating **Trade Plan**.
- An unexecuted **Trade Plan** does not receive a **Trade Review**.
- A **Trade Review** should always include a **Plan Execution Assessment**.
- **Trade Review** uses entry and exit review moments; there is no separate review type for unexecuted plans.
- **Trade Plans**, **Trade Records**, and **Trade Reviews** all belong to the **Journal** workflow.
- The **Journal** defaults to the active trade plan queue before trade record history.
- The default **Journal** plan queue shows `planned` trade plans only.
- Executed **Trade Plans** remain visible through filters, but their primary review path is through the linked **Trade Record**.
- Analysis outputs may prefill a **Trade Plan** form, but a complete plan is only created after the user confirms required baseline fields.
- Active **Trade Plans** are not injected into future analysis as feedback.
- A **Trade Plan** may record a **Plan Source**, but the source does not affect lifecycle status.
- **Trade Plans** use the same **Journal** read/write permissions as trade records and reviews.
- Plan identity and trade identity are distinct; a **Trade Plan** is identified separately from the **Trade Record** it may produce.
- A **Trade Plan** in `expired` status has no **Trade Record**.
- A **Trade Plan** in `executed` status has exactly one **Trade Record**.
- An unexecuted **Trade Plan** may be deleted; an executed **Trade Plan** must be retained.
- A **Trade Record** created from a **Trade Plan** carries both the originating plan identity and a **Trade Plan Snapshot**.
- A **Trade Record** created from a **Trade Plan** inherits plan fields for record defaults, while actual execution facts are entered on the record.
- A **Trade Review** compares execution against the **Trade Plan Snapshot**, not later edits to the **Trade Plan**.
- An executed **Trade Plan** must not have its **Execution Baseline** changed.
- An executed **Trade Plan** may still receive non-baseline edits that do not affect review judgment.
- A **Trade Plan** may carry **Analysis References**, but they are optional.
- **Analysis References** on a **Trade Plan** should be carried into the **Trade Plan Snapshot** when the plan becomes a **Trade Record**.
- A **Trade Plan Status Reason** is derived by the system; users may add notes, but notes do not determine whether a plan was executed.
- A **Trade Plan** must have a **Trade Plan Expiry**.
- A **Trade Plan Expiry** determines whether an unexecuted plan becomes `expired`; it is distinct from the expected holding period after execution.
- A **Trade Plan Expiry** is a concrete point in time, not a trading-day label.
- Expiry is judged when **Trade Plans** are read or otherwise touched by the system; it does not require a background scheduler.
- An expired **Trade Plan** may still be linked to a **Trade Record** when the record's actual entry time was within the plan's expiry window.
- An unplanned **Trade Record** may later link to a qualifying **Trade Plan** as a correction.
- A **Trade Plan** may use a **Planned Entry** instead of an exact entry price.
- A **Trade Plan** must define a **Reward Target**, but the target does not have to be an exact price.
- A **Trade Plan** must define a **Risk Rule**, but the rule does not have to be an exact stop-loss price.
- A **Trade Plan** must define a quantifiable **Position Plan**.
- A **Trade Plan** must contain enough required baseline fields to be executable and reviewable.
- A **Trade Record** can only link to a **Trade Plan** with the same instrument and direction.
- A **Trade Record** may link to a **Trade Plan** even when actual execution may have deviated from the planned entry conditions.
- A **Trade Record** may preserve actual execution facts that differ from the originating plan's position, risk, reward, or entry rules.
- Matching active **Trade Plans** may be suggested during trade record creation, but linking requires explicit user choice.

## Example Dialogue

> **Dev:** "If a planned MSFT breakout never triggers, do we create a trade record?"
> **Domain expert:** "No. It remains a **Trade Plan** without a **Trade Record**."
>
> **Dev:** "When reviewing a completed trade, do we only judge the PnL?"
> **Domain expert:** "No. The **Trade Review** should evaluate the **Trade Record** and compare it with the original **Trade Plan** when one exists."

## Flagged Ambiguities

- "交易预案" is distinct from **Trade Record** draft state; resolved: use **Trade Plan** as a first-class domain object that may never execute.
- "交易复盘" is not a standalone note; resolved: use **Trade Review** as an assessment tied to a **Trade Record**, with optional comparison to the originating **Trade Plan**.
- Multiple plans may inform judgment, but only one **Trade Plan** can be the execution source for a **Trade Record**.
- **Trade Plan Status** is intentionally limited to `planned`, `executed`, and `expired`; do not model manual cancellation as a separate status unless the product needs that distinction later.
- **Trade Plan Status Reason** is not a user-authored reason taxonomy; resolved: it exists only to explain the system's execution/expiry judgment.
- **Trade Plan Expiry** is required; resolved: do not allow open-ended trade plans.
- Expiry is compared as an absolute timestamp; resolved: do not model plan expiry as a market trading-day string.
- Expiry does not imply reminders or scheduled background work; resolved: query-time system judgment is enough for this workflow.
- Deletion is limited to unexecuted plans; resolved: executed plans are retained because they are part of the review baseline.
- Retroactive execution linking is allowed only to correct late data entry, not to justify trades entered after the plan expired.
- Unplanned trades are allowed; resolved: they are recorded as **Trade Records** without an originating **Trade Plan**, and **Trade Reviews** should treat that absence as an execution-discipline fact.
- Post-record plan linking is allowed only as correction when the plan is unused, instrument and direction match, and the record entry time falls within the plan expiry window.
- Plan linking is one-way in the first version; resolved: a **Trade Record** may move from no plan to one plan, but not from one plan to another.
- Unexecuted plans are not reviewed in the current journal workflow; resolved: **Trade Review** remains scoped to executed **Trade Records** only.
- **Plan Execution Assessment** is always visible in reviews; resolved: plan-linked trades compare against the **Trade Plan Snapshot**, while unplanned trades are explicitly marked as having no plan baseline.
- Do not introduce a separate plan review in the current workflow; resolved: plan execution judgment belongs inside entry and exit **Trade Reviews**.
- Do not introduce a separate top-level plans module in the current workflow; resolved: **Trade Plans** live inside **Journal**.
- **Journal** should reinforce planning-first behavior; resolved: show the trade plan queue before historical records by default.
- The plan queue is for actionable plans; resolved: `executed` and `expired` plans are available through filters rather than the default queue.
- Executed plans are read-only history in the plan list; resolved: the linked **Trade Record** is the main place to inspect execution and review.
- Creating a plan from an analysis report is a prefill workflow, not automatic plan creation; resolved: required plan fields must still be confirmed before the plan becomes `planned`.
- Analysis feedback remains review-based; resolved: active **Trade Plans** do not participate in historical feedback injection.
- **Plan Source** is metadata only; resolved: it supports audit and filtering without changing execution or expiry rules.
- Do not introduce separate plan permissions in the current workflow; resolved: **Trade Plans** inherit **Journal** permissions.
- Do not reuse trade identity for plans; resolved: use separate plan and trade identities so planned intent and executed facts remain distinct.
- Plan-linked records use a **Trade Plan Snapshot** for review; resolved: later plan edits must not rewrite the review baseline for an executed trade.
- **Execution Baseline** is immutable after execution; resolved: do not allow baseline correction by editing the originating **Trade Plan**.
- Non-baseline plan edits are allowed after execution; resolved: explanatory metadata may change without affecting the **Trade Plan Snapshot** or review baseline.
- Exact entry price is a **Trade Record** fact, not a required **Trade Plan** field; resolved: plans may specify entry conditions or zones instead.
- Incomplete trade ideas are not **Trade Plans** in this workflow; resolved: required baseline fields should guide users toward complete pre-trade planning habits.
- **Reward Target** may be textual; resolved: require a target rule, not necessarily a numeric take-profit price.
- **Risk Rule** may be textual; resolved: require an executable risk boundary, not necessarily a numeric stop-loss price.
- **Position Plan** must be quantifiable; resolved: vague sizing language is not enough for a complete **Trade Plan**.
- Incomplete planning does not block recording a **Trade Record**; resolved: it only prevents treating the trade as plan-based execution.
- Plan linking requires instrument and direction agreement; resolved: changing instrument or direction creates an unplanned **Trade Record**, not execution of the original **Trade Plan**.
- The system does not hard-block plan linking based on subjective entry-condition quality; resolved: **Trade Review** evaluates whether actual execution followed the **Planned Entry**.
- Execution deviations are review material, not save blockers; resolved: allow differing size, price, risk, reward, or entry details while preserving the original **Trade Plan Snapshot**.
- Do not auto-link matching plans; resolved: the system may suggest candidates, but the user chooses whether a **Trade Record** originates from a **Trade Plan**.
- Plan execution should reduce duplicate entry; resolved: copy plan terms into record defaults and use **Execution Note** for real-time context or deviations.
- **Analysis References** are optional supporting evidence; resolved: plans may exist without report links, but linked references should follow the plan into the executed record snapshot.
