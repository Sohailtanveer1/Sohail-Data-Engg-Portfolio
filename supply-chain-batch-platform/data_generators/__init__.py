"""Local source-system emulators for the Supply Chain Batch Data Platform.

Each module emulates one real source and writes its native format:
- sap_erp        -> CSV        (SFTP drop)
- salesforce     -> JSON       (served by the mock REST API)
- wms            -> CSV        (loaded into local Postgres)
- tms            -> Parquet    (GCS/cloud export)
- supplier_portal-> Excel .xlsx (SFTP drop, deliberately messy)

All modules share ``reference.py`` so business keys line up across sources
(a material in a SAP PO also exists in WMS inventory), which lets later phases
demonstrate real referential-integrity checks and conformed dimensions.
"""
