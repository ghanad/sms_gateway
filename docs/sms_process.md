### **Architecture Documentation: The "Simple & Robust" SMS Processing Engine**

#### 1. Overview

This document outlines the architecture for the `server-b` backend, which is responsible for reliably processing and sending SMS messages received from `server-a`. The primary design goals are **maximum reliability** (zero message loss), **high resilience** against temporary provider or network failures, and **clear, immediate feedback** to the end-user.

The architecture is a database-centric, multi-stage pipeline that separates the initial, safe ingestion of messages from the complex logic of sending, failover, and retries. This ensures that once a message is accepted into the system, it is never lost and every reasonable effort is made to send it.

#### 2. Core Principles

The entire system is built upon these foundational principles:

*   **No Message Loss:** A message is only removed from the initial RabbitMQ queue after it has been safely and transactionally persisted to the primary database. The database acts as the single source of truth for all messages.
*   **Intelligent Failure Handling:** The system distinguishes between **transient failures** (temporary issues like network timeouts or a provider being busy) and **permanent failures** (unrecoverable issues like an invalid recipient number). It will persistently retry on transient failures but will fail fast on clear permanent failures.
*   **User-Centric Feedback:** The system is designed to provide immediate and accurate status updates. A user will never be left with a vague "Processing" status for an extended period; they will know if their message is sent, failed permanently, or is awaiting a scheduled retry due to a temporary issue.
*   **Respect User Choice:** If a user specifies a preferred list of providers, the system will honor that list exclusively. Otherwise, it will perform a "smart selection" by attempting delivery across all active providers based on a predefined priority.

#### 3. The Lifecycle of an SMS Message: A Step-by-Step Workflow

The journey of a message from queue to final status follows a clear, multi-stage process:

1.  **Ingestion (The Consumer):**
    *   The `sms-consumer-b` service, running the `consume_sms_queue` management command, listens to the `sms_outbound_queue`.
    *   It fetches a message and immediately starts a database transaction.
    *   It creates a `Message` record with the status `PENDING` and saves the entire original message data (the "envelope") into a JSONField for future use.
    *   Only upon successful database commit does it acknowledge (`ack`) the message, removing it from RabbitMQ. This guarantees that the message now lives safely in our system.

2.  **Dispatching (The Scheduler):**
    *   The `celery-beat-b` service runs a periodic task, `dispatch_pending_messages`, every 10 seconds.
    *   This task queries the database for a batch of messages in the `PENDING` state.
    *   To prevent race conditions, it atomically updates their status to `PROCESSING`.
    *   For each message, it asynchronously triggers the main worker task, `send_sms_with_failover`, passing the `message_id`.

3.  **Execution (The Worker):**
    *   A `celery-worker-b` instance picks up the `send_sms_with_failover` task. This task contains the core sending and decision-making logic.
    *   **Provider Selection:** It first determines which providers to use—either the user-specified list from the envelope or all active providers ordered by priority.
    *   **Failover Loop:** It iterates through the selected providers and attempts to send the SMS.
    *   **Decision & Finalization:** After the loop, based on the outcomes of the attempts, it makes a final decision as detailed in the next section.

#### 4. The Core Logic: Failure Handling and Decision Matrix

This is the "brain" of the system, located within the `send_sms_with_failover` task.

**A. Provider Adapter Responsibility:**
Each provider's adapter (e.g., `MagfaSmsProvider`) is responsible for interpreting the API response and returning a standardized, structured dictionary:
*   **Success:** `{'status': 'success', 'message_id': '...'}`
*   **Permanent Failure:** `{'status': 'failure', 'type': 'permanent', 'reason': '...'}`
*   **Transient Failure:** `{'status': 'failure', 'type': 'transient', 'reason': '...'}`

**B. The Worker's Decision Logic (after the failover loop):**

| **Scenario** | **Condition** | **Action** |
| :--- | :--- | :--- |
| **1. Immediate Success** | One of the providers in the loop returned `SUCCESS`. | 1. Update `Message` status to `SENT_TO_PROVIDER`.<br>2. Store success details.<br>3. Task finishes. |
| **2. Permanent Failure** | The loop finished, no provider succeeded, AND at least one provider returned a `PERMANENT_FAILURE`. | 1. Update `Message` status to `FAILED`.<br>2. Store all accumulated error messages.<br>3. Publish the message to the **Dead Letter Queue (DLQ)**.<br>4. **Do not retry.** Task finishes. |
| **3. Transient Failure** | The loop finished, no provider succeeded, AND **all** failures were of type `TRANSIENT_FAILURE`. | 1. Update `Message` status to `AWAITING_RETRY`.<br>2. Store the last error message for user feedback.<br>3. **Schedule a retry** using Celery's exponential backoff mechanism.<br>4. If max retries are exceeded, transition to the "Permanent Failure" state (Step 2). |

#### 5. User Feedback Mechanism

*   The user interface will display the message's current status directly from the database.
*   When a message's status is `AWAITING_RETRY`, the UI will also display the content of the `error_message` field. This provides immediate context for the delay, such as "Provider temporarily unavailable. Will retry shortly."
*   When the status is `FAILED`, the UI will show the final, determinative error message, such as "Recipient number is invalid."

#### 6. Benefits of this Architecture

*   **Reliability:** The transactional hand-off from RabbitMQ to the database prevents message loss.
*   **Efficiency:** The system avoids wasteful retries for messages that are guaranteed to fail, while still being persistent for temporary issues. The database is only queried for pending work, avoiding constant polling of the entire table.
*   **Maintainability:** The logic is cleanly separated. Adapters handle provider-specifics, the consumer handles ingestion, and the worker handles the business logic of sending.
*   **Transparency:** At every stage, the message has a clear, accurate status in the database, which can be directly exposed to users and administrators for clear insight into the system's operation.