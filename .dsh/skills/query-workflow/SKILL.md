# query-workflow

Standard query workflow:

1. Establish the task contract before generating SQL.
2. Search candidate tables only when the semantic model does not already identify the source entity.
3. Resolve metric and dimensions.
4. If task type is `standard_query` and semantic coverage meets the program threshold, use the deterministic query engine.
5. Otherwise use the agentic analysis path; do not pretend a single metric query answers a causal/explanatory question.
6. Validate every SQL candidate.
7. Never request or fabricate credentials. All database access must cross the Agent3 controlled service boundary.
