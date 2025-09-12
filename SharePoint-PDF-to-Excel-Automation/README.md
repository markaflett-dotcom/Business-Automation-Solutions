## 1. High-Level Architecture

### Components (logical)

*   **File landing zone:** SharePoint Online document library (`InvoiceInbox`)
*   **Orchestration:** Power Automate (cloud flows) — main automation engine
*   **OCR / extraction:** Azure Form Recognizer (preferred) or AI Builder (alternate)
*   **Transient storage / queue:** SharePoint folders (`Processed`, `Exceptions`) and/or Dataverse table for metadata & dedupe
*   **Staging output:** Excel file in SharePoint (formatted for BC import) + optional Dataverse staging entity
*   **BC Integration:** Business Central Configuration Package (CSV/XLSX upload) or Business Central Web APIs (OData/REST)
*   **Monitoring & logging:** Dataverse or SharePoint log list; Power BI for operational dashboard; Azure Monitor for Form Recognizer
*   **Operator portal (optional):** Power Apps model-driven or canvas app for exception review and reprocessing
*   **Security & identity:** Azure AD App Registrations / Managed Identity, Conditional Access, Data Loss Prevention policies

### Logical flow (summary)

1.  New PDF arrives in SharePoint folder (`InvoiceInbox`).
2.  Power Automate triggered: copies file, calls OCR (Form Recognizer) to extract fields.
3.  Normalizes & validates data (formatDateTime, numeric checks, mandatory field checks, duplication check against processed index).
4.  **If valid,** write validated row to staging Excel file (exact BC format) and log success. Optionally push to BC via API or leave package for scheduled BC import.
5.  **If invalid,** move PDF to `Exceptions` folder, write details in exception log, notify exceptions queue (email/Teams) and create a review task in Power Apps.
6.  Monitoring and dashboards reflect processing volume, errors, latency.

### Rationale for Microsoft-centric approach

*   **Native integration:** SharePoint + Power Automate + Power Platform + Business Central are first-class citizens in Microsoft 365 and Dynamics ecosystems — minimal middleware and consistent security model (Azure AD).
*   **Rapid development & maintainability:** Power Platform reduces custom code, provides visual flow representation and ALM patterns (Solutions).
*   **Enterprise grade OCR:** Azure Form Recognizer provides high accuracy, model training for custom invoice layouts, and scalable performance; integrates via REST/API easily from Power Automate.
*   **Governance & Compliance:** Uses corporate tenants and established controls (DLP, Conditional Access), making it easier to satisfy security/compliance.
*   ## 2. Detailed Power Automate Flow

This section describes a production-grade Cloud Flow design. Use **Solutions** in Power Platform to package flows, Power Apps, and custom connectors.

**Flow: `Invoice_Ingest_Process_v1`** (trigger: When a file is created in a folder)

### Trigger
*   **Connector:** SharePoint
*   **Action:** `When a file is created (properties only)`
    *   **Site Address:** Client SharePoint site
    *   **Library Name:** `InvoiceInbox`
    *   **Folder:** `/Inbox`

### Initial file lock & metadata
1.  **Action:** `Get file metadata` — SharePoint `Get file properties` (ensures we have CreatedBy, Created date)
2.  **Action:** `Get file content` — SharePoint `Get file content` (binary for OCR)
3.  **Action:** `Create processing record` (Dataverse or SharePoint list) — Dataverse `Create a new row` (table: `InvoiceProcessingLog`)
    *   **Columns:** FileName, FileLink, ReceivedTimestamp, `Status=Processing`, CorrelationID (GUID)

### Call OCR/Extraction
4.  **Action:** `HTTP` / `Custom Connector` or `Azure Form Recognizer connector`
    *   **Option A (preferred):** Custom connector or `HTTP` action calling Azure Form Recognizer v3.0/v3.1 `Analyze` endpoint. Provide file content as multipart/form-data or Base64.
    *   **Option B:** AI Builder — Action: `Extract information from invoices` (if licensing forces staying within Power Platform).
    *   **Add headers:** `Ocp-Apim-Subscription-Key` (or use Managed Identity via Azure Function)
    *   **Response** -> JSON payload with detected fields.

### Parsing OCR Response
5.  **Action:** `Parse JSON` — Built-in `Parse JSON` action. Supply schema matching Form Recognizer output. Outputs mapped to variables:
    *   `invoiceNumber`, `vendorName`, `vendorTaxID`, `invoiceDate`, `dueDate`, `currency`, `subtotal`, `taxAmount`, `totalAmount`, `lineItems` (array)

### Data Normalization
6.  **Action:** `Initialize variables` — for each field (string/integer/float/date).
7.  **Action(s):** Normalization expressions (examples below):
    *   **Invoice date normalizing:** `formatDateTime(coalesce(body('Parse_JSON')?['invoiceDate'],'1900-01-01T00:00:00Z'),'yyyy-MM-dd')`
    *   **Number normalization:** `float(replace(replace(trim(outputs('Parse_JSON')?['totalAmount']),',',''),'$',''))`
    *   **Trim vendor name:** `trim(coalesce(body('Parse_JSON')?['vendorName'],'Unknown Vendor'))`

### Validation rules (basic)
8.  **Action:** `Condition` — Evaluate validations:
    *   **Mandatory fields present:** `invoiceNumber != empty AND totalAmount > 0 AND invoiceDate is a valid date`
    *   **Numeric checks:** `and(greater(float(totalAmount),0), greaterOrEquals(float(taxAmount),0))`
    *   **Date sanity:** `invoiceDate <= utcNow()`
    *   **Duplicate detection:** Query processed index (Dataverse/SharePoint) for same `vendor + invoiceNumber + amount` within last 365 days
    *   If any validation fails: go to **Exception branch**

### Valid branch
9.  **Action:** `Update staging storage` — two options:
    *   **Append row to Excel (SharePoint):** Connector: `Excel Online (Business)` Action: `Add a row into a table`
        *   **File:** `BC_Import_Staging.xlsx` in library `/Staging`
        *   **TableName:** `tblInvoicesForBC`
        *   Map fields to columns exactly as required (see Section 4).
    *   Alternatively, Create a Dataverse row in `Invoices_Staging` and use a scheduled job to convert to Excel.
10. **Action:** `Move file to Processed folder` — SharePoint `Move file` to `/Processed/YYYY/MM/`
11. **Action:** `Update processing record` — Dataverse `Update row` (`status = Processed`, `BCStatus = Ready`, `ProcessedTimestamp`)
12. **Optional Action:** `Call Business Central API` (if chosen): `HTTP POST` to BC Sales/Purchase Invoice API with JSON body built from mapped fields (authentication via Azure AD app registration). On success update `BCDocumentNo`.

### Exception branch
13. **Action:** `Move file to Exceptions folder` — SharePoint `Move file` to `/Exceptions/`
14. **Action:** `Create exception log` — Dataverse `Create row` (`InvoiceExceptions`) with file link, parsed values, validationErrors (stringified), OCRConfidence, and correlationID.
15. **Action:** `Notify / Task creation` — Send an adaptive card to Teams channel or send an email to AP group with link to file and action buttons (`Reprocess` / `Mark as Manual`). Optionally create a Power Automate approval or Power Apps task for human review.

### Post-processing
16. **Action:** `Increment processing metrics` — write to `ProcessingMetrics` table (counts, latency)
17. **Action:** `Termination / Logging` — Update main processing log with final status.

### Key Power Automate expressions (examples)
*   **Normalize date (ensure standard format):**
    `formatDateTime(coalesce(triggerOutputs()?['body/InvoiceDate'],'1900-01-01T00:00:00Z'),'yyyy-MM-dd')`
*   **Remove commas & currency symbol then convert to float:**
    `float(replace(replace(trim(outputs('Parse_JSON')?['totalAmount']),',',''),'$',''))`
*   **Coalesce with default:**
    `coalesce(body('Parse_JSON')?['vendorName'],'Unknown Vendor')`
    ## 3. OCR / Extraction Strategy

**Recommendation: Azure Form Recognizer (Custom Invoices model) — preferred for enterprise**

**Why:**
*   **Higher accuracy** and advanced layout understanding (table extraction, line items, nested fields).
*   **Supports custom-trained models** for the client's vendor templates and can improve with active learning.
*   **Scalable** and provides **confidence scores** for fields, enabling robust validation thresholds.
*   **Direct API integration** with Power Automate via HTTP/custom connector or Azure Function for retry/fallback logic.
*   **Auditability** — can store raw output and training data for tracing errors.

**Alternate: AI Builder (Invoice processing)** — easier to set up directly in Power Platform but:
*   Simpler licensing model if the client has AI Builder capacity.
*   Less control and limited in advanced layout handling compared to Form Recognizer.
*   Choose AI Builder if client cannot provision Azure Cognitive Services or prefers fully platform-native approach.

### Model training process (Form Recognizer)
1.  **Collect sample invoices** — gather a representative training set (~50–200 documents) across major vendor layouts, languages, currencies, and varying image quality.
2.  **Label data** (if creating custom layout or supervised model): use Form Recognizer labeling tool (Form Recognizer Studio) to tag fields: `InvoiceNumber`, `InvoiceDate`, `VendorName`, `VendorTaxID`, `LineItems` (Description, Qty, UnitPrice, LineAmount), `Totals`, `Currency`.
3.  **Train model** — create a custom model (prebuilt/invoice + custom if necessary). Version & tag the model.
4.  **Evaluate & iterate** — run validation set, review field confidence scores, flag low-confidence fields for review or model retraining.
5.  **Promote to production** — deploy model endpoint and update Power Automate to use production model ID.
6.  **Feedback loop** — capture corrected values from manual review via Power Apps and feed back labeled examples to retrain periodically (monthly/quarterly).

### Handling line items
*   Form Recognizer returns `lineItems` as an array. In Power Automate iterate over `lineItems` and summarize into required BC format (BC often expects header-level totals; if BC requires lines, construct additional rows in staging Excel or use API line creation).
*   For complex multi-line invoices, store raw JSON in a staging blob or Dataverse field for audit.
*   ## 4. Excel Template & Business Central Integration

### Excel Template (Single sheet `Invoices_for_BC`)

Create an Excel workbook **`BC_Import_Staging.xlsx`** with an Excel Table **`tblInvoicesForBC`** (named range) in SharePoint. The columns below are designed to import purchase invoices to Business Central using a Configuration Package or map to BC API fields.

**Recommended column headers** (ensure exact names when mapping to BC import):
*   `Document Type` — (e.g., Purchase Invoice)
*   `Document No.` — (Vendor invoice number)
*   `Vendor No.` — (Business Central vendor number — if unknown may be blank and mapped later)
*   `Vendor Name`
*   `Vendor Tax ID` — (ABN / VAT number)
*   `Posting Date` — (YYYY-MM-DD)
*   `Invoice Date` — (YYYY-MM-DD)
*   `Due Date` — (YYYY-MM-DD)
*   `Currency Code` — (e.g., USD, AUD)
*   `Purchase Currency Factor` — (1.0 if same currency)
*   `Document Currency Code` — (if needed)
*   `Amount (Excl. VAT)` — (decimal)
*   `Tax Amount` — (decimal)
*   `Amount (Incl. VAT)` — (decimal)
*   `Tax Code` — (e.g., GST, VAT0)
*   `Description` — (header-level description)
*   `Payment Terms Code`
*   `Payment Method Code`
*   `Reference` — (internal reference)
*   `Source File Link` — (link to invoice PDF in SharePoint)
*   `OCR Confidence` — (summary confidence, e.g., 0.92)
*   `LineItemsJson` — (optional: line items as JSON if BC integration will create lines via API)
*   `ProcessedFlag` — (Yes/No)
*   `ProcessedDate`

**Note:** Exact schema can vary by client BC setup. Confirm BC import mappings and required fields with the BC admin.
### Business Central Import Methods

#### Method A — Configuration Package (Batch Import via Excel/CSV)
1.  Export a template from BC Configuration Packages for Purchase Invoices (Table: `Purch. Inv. Header` and `Purch. Inv. Line`).
2.  Populate header & lines in the package format.
3.  Operator uploads package in BC or automate the upload using BC APIs that import configuration packages.
*   **Pros:** Works with built-in BC import tooling; lower API complexity.
*   **Cons:** Manual step unless automated via script/API; may require mapping adjustments per BC version and localization.
#### Method B — Business Central APIs (Recommended for full automation)
1.  Use BC Purchase Invoice API endpoints (e.g., `POST /company({id})/purchaseInvoices`) or the `purchaseInvoices/purchaseInvoiceLines` endpoints.
2.  Authenticate using OAuth 2.0 with Azure AD app registration with delegated or application permissions.
3.  For each invoice:
    *   Create Purchase Invoice header via `POST`.
    *   `POST` line records to invoice lines endpoint.
    *   Finalize/post the invoice if required via a specific API (check BC version endpoints).
    *   **Pros:** Fully automated, real-time, better error handling, immediate feedback from BC (document numbers, errors).*   **Cons:** Requires API familiarity and additional permissions; consider throttling and API limits.

**Decision guidance:** If the client expects fully automated, low-latency posting to BC, use APIs. If they prefer operator verification and batch import, use Configuration Packages and schedule imports.
## 5. Validation & Error Handling Process

### Validation rules (header level)
*   **Mandatory fields:** `Invoice Number`, `Invoice Date`, `Amount (Incl. VAT)` must be present.
*   **Numeric checks:** `Amount(Incl)` and `Tax` must be numeric > 0 (or zero if no tax).
*   **Date checks:** `InvoiceDate` ≤ `ReceivedDate` and `InvoiceDate` not in future by >30 days (configurable).
*   **Currency check:** Currency code must be valid ISO code or match vendor default.
*   **Vendor mapping:** If `Vendor No.` is provided, it must exist in BC; otherwise flag to vendor resolution queue.
*   **Line totals check:** `Sum(LineAmount)` ≈ `Amount(Incl/Totals)` within tolerance threshold (e.g., 0.5%)
*   **Duplicate detection:** Search processed index for same `Vendor + InvoiceNo` OR same `Vendor + Amount + InvoiceDate` within 365 days.
*   **OCR confidence threshold:** If primary fields (`InvoiceNumber`, `Total`, `Date`) confidence < configured threshold (e.g., 0.75), flag for human review.

### Exception handling workflow
*   **Classification of exceptions:**
    *   **Soft exception:** Missing non-critical field, low confidence — route to human verification queue (Power Apps) with prefilled parsed values for correction.
    *   **Hard exception:** Missing critical field, failed numeric/date validation, or duplicate — move to `Exceptions` folder and create incident.
*   **Actions on exception:**
    1.  Move PDF to `/Exceptions/{YYYY}/{MM}/`.
    2.  Create an exception record (Dataverse) with: `CorrelationID`, `FileLink`, `extractedFields`, `validationErrors`, `OCRResponse`, `ReceivedTimestamp`.
    3.  Notify AP team via Teams adaptive card + email — include actions: `View & Edit`, `Reprocess` (after human fix), `Ignore/ManualPost`.
    4.  Optionally create a task in Planner or a Power Apps queue for assignment.
*   **Human-in-loop correction:** Use a simple Power App form that loads exception record, allows editable fields, and a `Reprocess` button to re-run the same flow against corrected data.
*   **Retry logic:** For transient errors (OCR service timeout, BC API throttling), implement exponential backoff retries (3 attempts). Log all retry attempts.
*   **Error logging & retention**
    *   Record every attempt in `InvoiceProcessingLog` table with timestamps (Received, OCR Completed, Validated, Staged, BCPosted), error codes and full OCR JSON for debugging.
    *   Retain logs per retention policy (e.g., 7 years for audit, or per client policy).
    *   ## 6. Monitoring, Logging & Security

### Logging & telemetry
*   **Primary logs** (Dataverse or SharePoint list): `InvoiceProcessingLog` with columns: `CorrelationID`, `FileName`, `User`, `ReceivedUTC`, `OCRDuration`, `ValidationStatus`, `ErrorCodes`, `FinalStatus`, `BCReferenceNo`, `ProcessedUTC`.
*   **Exception logs:** `InvoiceExceptions` table containing the full OCR JSON, validation errors, manual notes, and who resolved it.
*   **Metrics:** Counters for processed per hour/day, average processing time, exceptions rate, top failing vendors, OCR confidence distributions.

### Monitoring & dashboards
*   **Power BI dashboard:** connect to Dataverse or SharePoint log lists to display:
    *   Throughput (invoices / day)
    *   Success rate & exception trends
    *   Avg processing time & SLA breaches
    *   Top vendors by volume & error count
    *   Recent exceptions with links to SharePoint
*   **Alerts:** Configure Power Automate / Power BI alerts + Azure Monitor alerts for:
    *   Exception rate > threshold (e.g., >5% daily)
    *   Failure of OCR service
    *   BC API authentication failures
*   **Health checks:** Scheduled flow to probe critical components:
    *   Heartbeat flow that creates a health record hourly
    *   Synthetic tests: upload small PDF, verify end-to-end success

### Security & best practices
*   **Identity & access**
    *   Use Managed Identity or Azure AD Application (service principal) for service-to-service authentication where possible.
    *   Grant least privilege to SharePoint site, Dataverse tables, and BC API scopes.
    *   Use separate service accounts or app registrations for production vs. dev/test.
*   **Secrets & keys**
    *   Store keys and secrets in Azure Key Vault and reference via Managed Identity or use Power Platform connection references with environment-level connectors.
*   **Data protection**
    *   Encrypt data-at-rest with Azure/Office 365 encryption controls. Ensure SharePoint sensitive columns are secured.
    *   Use DLP policies in Power Platform to avoid data exfiltration.
*   **Transport security**
    *   All communications via HTTPS/TLS. Use OAuth 2.0 for BC API.
*   **Auditing & compliance**
    *   Enable audit logs in Power Platform and SharePoint. Keep change history for flows and Dataverse.
*   **Operational access**
    *   Use role-based access control (RBAC) for Power Platform admin roles, and an AP operator role for exception handling.
*   **Network Controls**
    *   If required, limit access to Form Recognizer endpoint via service tags and VNet integration.
    *   ## 7. Testing & Handover Plan

### Testing approach
1.  **Unit Tests (Component-level)**
    *   Test OCR output for a set of representative single-page invoices.
    *   Validate Power Automate actions: parsing, normalization expressions, numeric/date conversions.
    *   Test duplicate detection logic with test entries in staging database.
2.  **Integration Tests**
    *   End-to-end tests: upload sample invoices to SharePoint; assert output row appears in `BC_Import_Staging.xlsx` and file moved to `Processed`.
    *   Test exceptions: corrupt invoice, missing fields, low confidence, and ensure exception workflow works (file moved to `Exceptions`, notification created).
    *   BC Integration test environment: post data to a BC sandbox using API or import a configuration package. Validate mapping correctness (header & lines).
3.  **User Acceptance Testing (UAT)**
    *   Provide AP team a UAT environment with 100 varied invoices (realistic set). Track acceptance criteria:
        *   Accuracy threshold (e.g., 95% on header fields).
        *   Exception handling and reprocessing usability.
        *   BC import mapping correctness.
    *   Collect feedback, refine model and flow logic.
4.  **Load and Performance Testing**
    *   Throughput test to ensure system can process expected daily volume (e.g., 1,000 invoices/day) and burst scenarios.
    *   Test Form Recognizer concurrency limits and Flow concurrency settings.
    *   Measure avg latency and SLA adherence.
5.  **Security & Compliance Testing**
    *   Penetration test for access controls.
    *   Verify RBAC and secret access.

### Test artifacts
*   Test plan & matrix (cases, expected results)
*   Test data set (anonymized invoices)
*   Test run results and defect log

### Handover deliverables (operator & technical)
Deliver a professional handover pack including:

**Technical artifacts**
*   Full Solution Architecture Document (this document).
*   Power Automate export (Solution package `.zip`) and step-by-step deployment instructions.
*   Azure resources ARM templates or Bicep scripts for Form Recognizer & Key Vault provisioning.
*   Custom connector definition (if used) / API spec and sample requests.
*   Dataverse table definitions & sample data.
*   Excel template `BC_Import_Staging.xlsx` with table definition.
*   Power Apps (if used) solution package for exception processing.

**Operational documentation**
*   **Operator Runbook** (must include):
    *   Daily checklist (e.g., check queue, exceptions, disk/SharePoint quotas).
    *   How to view logs (Dataverse/SharePoint) and run Power BI dashboard.
    *   How to reprocess an exception (Power Apps instructions).
    *   How to manually upload Excel to BC (if operator chooses Configuration Package).
    *   Incident procedures and escalation contacts.
*   **Admin Runbook:**
    *   How to rotate keys, update Azure AD app credentials.
    *   How to update OCR model and promote to production.
    *   How to update Power Automate flow and deploy via ALM/solutions.
*   **Support SLA document**
    *   Expected response times for P1/P2/P3 incidents.
    *   Contact list & escalation path.

**Training materials**
*   Quick start guide for AP users (1-page cheat sheet).
*   Walkthrough video (recommended) for operation and exception handling.

**Maintenance schedule & lifecycle**
*   Monthly model retraining cadence, quarterly review of exceptions, yearly archive policy.

**Handover checklist**
*   All artifacts delivered (Solution package, runbooks, templates).
*   UAT sign-off from AP and IT security.
*   Permissions & RBAC validated.
*   Support contact and SLAs agreed.
*   Backup & disaster recovery validated.
*   ## 8. Deployment & ALM Recommendations

### Environments
*   Dev, Test, UAT, Prod (separate Power Platform environments, SharePoint libraries, and Form Recognizer resource endpoints).

### ALM (Application Lifecycle Management)
*   Keep Power Automate flows, Power Apps and Dataverse entities inside a **Solution** and use Solution export/import for promotion.
*   **Source control:** export flow definitions to source repo (Power Platform CLI / GitHub Actions).
*   Use CI/CD pipelines to import solutions between environments (Power Platform Build Tools or GitHub Actions).
*   Azure resources deployed via ARM/Bicep templates.
*   Maintain versioned Form Recognizer models and keep model metadata in source control.
*   ## 9. Estimated Licensing & Cost Considerations (high-level)

*   **Power Automate:** Premium connectors (HTTP, Custom Connector) and AI Builder/Dataverse usage may require Power Automate per-user/per-flow plans.
*   **Azure Form Recognizer:** Cognitive Services consumption-based pricing (per page). Costs depend on invoice volume and number of pages.
*   **Dataverse:** If used, requires Power Apps per-user or capacity licenses. Alternatively, use SharePoint lists to minimize cost but trade off relational features.
*   **Business Central API usage:** Licensing depends on BC tenant type and whether APIs require premium permissions.

**NOTE:** Provide accurate cost estimates during procurement; confirm with Microsoft licensing specialist.
## 10. Operational Runbook (Concise, actionable)

### Daily operator tasks
1.  Check Power BI dashboard for yesterday's processing summary.
2.  Open `Exceptions` folder — triage new exceptions (assign to AP user).
3.  Check `InvoiceProcessingLog` for any flow failures and restart failed runs if transient.
4.  Ensure `BC_Import_Staging.xlsx` is present and scheduled BC import (if not using API) is still in place.
5.  Confirm Form Recognizer monthly credit consumption and forecast.

### How to reprocess a failed invoice (operator)
1.  Open exception record in Power Apps (link in Teams or log).
2.  Correct parsed fields as required (InvoiceNo, Date, Amount, Vendor).
3.  Save and click `Reprocess` (this triggers a Power Automate rerun with corrected data).
4.  Verify artifact moved to `Processed` and staging row present.

### Incident handling
*   **OCR service failure:** Verify Azure Form Recognizer resource, check quota and keys in Key Vault. Contact Cloud infra team and escalate to MS Support.
*   **BC API authentication error:** Verify Azure AD app secret or managed identity status; check token acquisition logs.
*   **High exception rate:** Stop automatic BC posting (safest option), notify AP and run root cause analysis.

### Backup & restore
*   Export `BC_Import_Staging.xlsx` daily to an Archive folder with date stamp.
*   Export Dataverse backups using environment backup policies.
*   Keep monthly snapshots of Form Recognizer models and labeled data.
*   {
    "type": "object",
    "properties": {
        "invoiceNumber": {"type": "string"},
        "vendorName": {"type": "string"},
        "vendorTaxId": {"type": "string"},
        "invoiceDate": {"type": "string"},
        "dueDate": {"type": "string"},
        "currency": {"type": "string"},
        "subtotal": {"type": "number"},
        "taxAmount": {"type": "number"},
        "totalAmount": {"type": "number"},
        "confidence": {"type": "number"},
        "lineItems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unitPrice": {"type": "number"},
                    "lineAmount": {"type": "number"}
                }
            }
        }
    }
}
## Appendix B — Example Power Automate step map (concise)

1.  **Trigger:** `SharePoint - When a file is created (properties only)`
2.  `SharePoint - Get file content`
3.  `HTTP (POST) → Form Recognizer Analyze endpoint` (or `AI Builder - Extract information from invoices`)
4.  `Parse JSON`
5.  `Compose / Set variables` (normalization)
6.  **Condition:** Validation checks (mandatory, numeric, duplicate)
    *   **7a. If Valid** → `Excel Online (Business) - Add a row into a table` → `Move file (Processed)` → `Update logs`
    *   **7b. If Invalid** → `Move file (Exceptions)` → `Dataverse - create exception` → `Notify Teams/Email`

## Appendix C — Security checklist (pre-prod → prod)

- [ ] Create Azure AD app registrations for service principal usage with least privileges.
- [ ] Put secrets into Azure Key Vault, use Managed Identity for retrieval.
- [ ] Limit SharePoint document library permissions (AP group write, all others read only).
- [ ] Confirm DLP policies in Power Platform prevent copying to unsafe connectors.
- [ ] Ensure Power Automate environments follow tenant development lifecycle and governance rules.
- [ ] Setup MFA & Conditional Access for admin accounts.
