# bootstrap/

One-time Terraform that creates the prerequisites for the main stack: the
versioned GCS **remote-state bucket** and the **CI deployer service account**.
Applied once before any environment. **Populated in Phase 3.**
