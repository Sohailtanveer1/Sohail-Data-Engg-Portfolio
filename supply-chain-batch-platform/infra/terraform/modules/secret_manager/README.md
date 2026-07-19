# Module: secret_manager

Creates secret *containers* (SAP SFTP password, Salesforce token, WMS DB
password, …) and grants `secretAccessor` to the SAs that need them. **Secret
values are never in Terraform** — add them out-of-band:

```
echo -n "$SECRET" | gcloud secrets versions add scb-dev-sap-sftp-password --data-file=-
```

**Inputs:** `project_id`, `name_prefix`, `secret_names`, `accessors`
(`{secret, member}`), `labels`.
**Outputs:** `secret_ids`.

Auto replication for the portfolio; CMEK/rotation is the enterprise upgrade
(cost doc §7).
