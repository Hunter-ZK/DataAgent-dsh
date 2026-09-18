# dw-ddl-standard

- DDL is a write operation and must never be executed through `bash` against production.
- Build and validate the DDL as a candidate first.
- Production submission must use `mcp__agent3__submit_ddl` after the production execution stage is explicitly enabled.
- Approval must fail closed: only an explicit one-time grant is accepted.
- Partitioning, lifecycle, owner, comments, and naming must be present when required by enterprise standards.
