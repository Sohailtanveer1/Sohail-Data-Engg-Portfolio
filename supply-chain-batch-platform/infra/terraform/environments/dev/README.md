# environments/dev/

Terraform root for the **dev** environment. Composes the shared modules via
`main.tf` + `dev.tfvars`. Cost-risky compute (Dataproc/Composer) is added in
Phases 6/8 — Phase 3 is foundation only.

```bash
cp backend.hcl.example backend.hcl          # set state bucket from bootstrap
# edit dev.tfvars: project_id, billing_account
terraform init -backend-config=backend.hcl
terraform apply  -var-file=dev.tfvars
terraform destroy -var-file=dev.tfvars       # clean teardown
```

Full apply runbook (incl. bootstrap + secrets):
[docs/phase-03-terraform-foundation.md](../../../../docs/phase-03-terraform-foundation.md#runbook--apply-the-foundation-you-drive-this).
