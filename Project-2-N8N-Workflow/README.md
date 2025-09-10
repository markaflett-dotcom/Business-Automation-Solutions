# Project 2: N8N LinkedIn Lead Generation & Nurture Workflow

### Project Overview
For this portfolio piece, I designed a comprehensive, two-part automation system that handles the entire client acquisition workflow on LinkedIn. The goal was to create a "hands-off" process that intelligently manages initial outreach, synchronizes all data with a CRM, and nurtures new connections to encourage meeting bookings.

This solution demonstrates an understanding of not just individual tools, but how to architect them into a cohesive and efficient business system.

### Core Technologies
*   **Orchestration:** N8N
*   **Outreach & Data:** Dux-Soup, LinkedIn
*   **CRM:** HubSpot
*   **Scheduling:** Calendly

---

### How The System Works

The solution is built around two core workflows that run in parallel to manage different stages of the client relationship.

1.  **The Outreach Workflow:** This is a real-time system that activates the moment a new lead is identified, handling the first contact and all initial data entry.
2.  **The Nurture Workflow:** This is a scheduled system that runs daily to check for new connections and follows up with them at the perfect time.

---

### A Step-by-Step Look at the Workflows

#### **Workflow 1: Initial Outreach & CRM Sync**

This workflow is all about speed and accuracy, ensuring no lead is missed.

*   **Step 1: The Trigger - Instant Lead Capture**
    Everything kicks off the moment Dux-Soup identifies a new lead on LinkedIn. It sends the lead's data (name, title, company, etc.) to a custom N8N webhook, which acts as the instant starting pistol for the entire process.

*   **Step 2: Crafting the Message**
    The system immediately uses the lead's data to generate a personalized and context-aware connection request message. This ensures the outreach feels personal, not automated.

*   **Step 3: Sending the Connection Request**
    With the message ready, the workflow sends a command to Dux-Soup to execute the connection request on LinkedIn, using the personalized message.

*   **Step 4: Creating the CRM Record**
    To keep the database clean and organized, the workflow connects to HubSpot. It intelligently checks if the contact already exists and, if not, creates a new record using the lead's data. This vital step prevents duplicate entries.

*   **Step 5: Logging the Activity**
    Finally, the system logs the connection request as a "Note" on the new contact's timeline in HubSpot. This provides a full audit trail, ensuring the sales team always knows which leads have been contacted and what was said.

#### **Workflow 2: The Follow-Up - Smart Nurturing**

The key to effective networking is the follow-up. This workflow handles that automatically.

*   **Step A: The Daily Kick-Off**
    This workflow isn't waiting for an event; it runs on a schedule. Once a day, it automatically starts, ready to check for new developments.

*   **Step B: Finding New Connections**
    The first thing it does is ask Dux-Soup for a list of everyone who has accepted a connection request in the last 24 hours. This gives us a fresh, daily list of warm leads to engage with.

*   **Step C: Sending the Booking Link**
    For each new connection, the system automatically sends a polite, pre-written follow-up message. This message thanks them for connecting and provides them with a direct Calendly link to book a meeting, striking while the iron is hot.

*   **Step D: Closing the Loop in the CRM**
    Just as before, every action is recorded. The workflow finds the corresponding contact in HubSpot and logs this second follow-up message on their timeline, maintaining a perfect history of our interaction.
