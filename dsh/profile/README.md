# dsh profile deployment

Pinned CLI: `@deepseek-ai/dsh@0.1.6-alpha.2`.

1. Initialize a profile: `dsh --profile dataagent --from-default-profile web`.
2. Copy `cordis.patch.yml` into `$DSH_HOME/profiles/dataagent/cordis.patch.yml`.
3. Install the built local `guard-plugin` package/tarball.
4. Export `DSH_TELEMETRY_MODE=DISABLED` and `LOCAL_LLM_KEY`.
5. Run `dsh --profile dataagent --dump-config` and treat any unmatched patch target as release-blocking.
6. Verify public egress is zero using network controls/observation.

The runtime account must not possess production database credentials and must not route to production database endpoints.
