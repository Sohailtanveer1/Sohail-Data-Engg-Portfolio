# environments/prod/

Terraform root for the **prod** environment. Composes shared modules via
`main.tf` + `prod.tfvars`. Cost-risky resources (Composer) are off by default.
