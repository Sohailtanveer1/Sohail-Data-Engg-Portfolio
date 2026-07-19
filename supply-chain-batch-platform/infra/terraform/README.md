# infra/terraform/

All infrastructure as code. Reusable `modules/` composed per environment in
`environments/{dev,uat,prod}/`. `bootstrap/` creates the remote-state bucket and
CI deployer SA. Remote state in GCS, one prefix per env. See
[ADR-0008](../../docs/adr/0008-terraform-environments.md). **Populated in Phase 3.**
