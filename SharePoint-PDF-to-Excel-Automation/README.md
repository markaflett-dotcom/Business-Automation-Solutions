# Automated PDF Invoice Processing for Business Central

### Project Overview
This document outlines a complete solution design for a common business challenge: the manual, error-prone process of transferring data from PDF invoices into an ERP system. The goal is to create a fully automated, "lights-out" workflow that monitors a document repository, intelligently extracts key information, and formats it perfectly for seamless integration with Microsoft Dynamics 365 Business Central.

This solution is designed to be robust, maintainable, and to provide full visibility into the process, effectively eliminating manual data entry and its associated costs and errors.

### Core Technologies
*   **Orchestration:** Microsoft Power Automate
*   **Document Storage:** Microsoft SharePoint
*   **Intelligent Extraction (OCR):** Power Automate AI Builder
*   **Data Output:** Microsoft Excel Online
*   **Target ERP System:** Microsoft Dynamics 365 Business Central

---

### The Solution Architecture: A Step-by-Step Breakdown

My design is built as a logical, five-step flow within Power Automate, with a dedicated "safety net" for handling any exceptions.

#### **Step 1: The Trigger - Instant File Detection**
The entire process kicks off automatically. We'll use the SharePoint connector in Power Automate with the trigger "When a file is created in a folder." The moment a new PDF invoice is dropped into the designated SharePoint folder, the workflow begins instantly. This removes the need for any manual start or batch processing.

#### **Step 2: The Brain - Intelligent Data Extraction**
This is the core of the automation. We will leverage Power Automate's **AI Builder** to create a custom document processing model. The process is straightforward:
1.  **Training:** We'll start by training the AI model with 5-10 sample PDF invoices. We'll visually tag the key fields the client needs (Invoice Number, Vendor Name, Total Amount, Date, etc.).
2.  **Execution:** In the flow, the "Extract information from documents" action will then be able to intelligently scan any *new* incoming PDF—even if the layout is slightly different—and accurately extract the data we trained it to find.

#### **Step 3: The Assembly Line - Data Validation & Formatting**
Raw data from an OCR process is rarely perfect. This step ensures the data is clean before it goes any further. For each piece of extracted information (like the invoice total), we will perform basic validation checks. For example, we'll check if the "Total" field contains a valid number or if the "Date" field is not empty. This prevents corrupted data from being passed downstream.

#### **Step 4: The Output - Seamless ERP Integration**
With the data cleaned and validated, the final action is to populate the Excel spreadsheet. We'll use the Excel Online connector's "Add a row into a table" action. The flow will map each piece of extracted data to the correct column in an Excel file that is pre-formatted to match the exact import specifications for Business Central. The end result is a perfectly clean, machine-readable file, ready for one-click import.

#### **Step 5: The Safety Net - Robust Error Handling**
No automated process is infallible. The key to a professional solution is planning for exceptions. Our workflow will include a dedicated error-handling branch.
*   **Catching Failures:** If the AI Builder model fails to read a PDF (e.g., it's a blurry scan) or if a key field is missing during validation, the flow will automatically catch this error.
*   **Actionable Alerts:** Instead of just failing silently, the flow will execute a "failure" branch that:
    1.  Sends a notification email to the operations team, detailing the error and which file was affected.
    2.  Moves the problematic PDF from the main folder into a separate "Manual Review Required" folder in SharePoint.
    
This ensures that the automated process never becomes a black box. The team is immediately alerted to any exceptions, and problematic files are automatically quarantined for human review, while the main process continues to run smoothly for all valid invoices.
