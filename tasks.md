
Hello! I need you to help me implement a new feature for my SMS Gateway project. The goal is to track the final delivery status of SMS messages after they have been sent to a provider.

Please follow this multi-phase plan step-by-step. Do not proceed to the next phase until the current one is complete.

**Project Context:**
The system has two main services: `server-a` (FastAPI) and `server-b` (Django/Celery). All the changes will be applied to `server-b`. The system uses an adapter pattern (`BaseSmsProvider`) to interact with different SMS providers. The task is to add functionality to query the final delivery status from providers that support it (like "Magfa," whose documentation is available) and update our database accordingly.

---

### **Phase 1: Database Model and Migration**

Your first task is to update the database schema to store the final delivery timestamp.

1.  **Modify the `Message` Model:**
    *   Locate the `Message` model in `server-b/messaging/models.py`.
    *   Add a new `DateTimeField` named `delivered_at`.
    *   This field should allow `null` and `blank` values, as not all messages will have a final delivery timestamp immediately (or ever).
    *   Include a helpful `help_text` for the new field, explaining that it stores the timestamp when the provider confirmed final delivery.

2.  **Create and Apply Database Migration:**
    *   After modifying the model, generate a new database migration file for the `messaging` app using Django's `makemigrations` command.
    *   Ensure the migration is correctly created and then apply it using the `migrate` command.

---

### **Phase 2: Enhance the Provider Adapter Layer**

Next, you will extend the provider adapter layer to handle status-checking capabilities in a flexible way.

1.  **Update the `BaseSmsProvider` Class:**
    *   Locate the `BaseSmsProvider` class in `server-b/providers/adapters.py`.
    *   Add a new property to this base class called `supports_status_check`. This property should return `False` by default. This will be our capability flag.
    *   Add a new method signature called `check_status(self, message_ids: list) -> dict`. This method should raise a `NotImplementedError` in the base class.

2.  **Implement Status Checking in the `MagfaSmsProvider` Adapter:**
    *   Locate the `MagfaSmsProvider` class, which inherits from `BaseSmsProvider`.
    *   Override the `supports_status_check` property to return `True`.
    *   Implement the `check_status` method. This method should:
        *   Accept a list of provider-specific message IDs.
        *   Make an HTTP GET request to the Magfa `statuses` API endpoint (refer to `docs/MAGFA.md` for the URL and structure).
        *   Parse the JSON response from the provider.
        *   Return a dictionary that maps each message ID to its final status (e.g., `'DELIVERED'` or `'FAILED'`) and the corresponding delivery timestamp (`date` from the provider's response).

---

### **Phase 3: Create the Background Status-Checking Task**

Now, create a periodic Celery task to use the new adapter functionality to update message statuses.

1.  **Create a New Celery Task:**
    *   In `server-b/messaging/tasks.py`, create a new Celery shared task named `update_delivery_statuses`.

2.  **Implement the Task Logic:**
    *   The task should query the `Message` model for messages that meet the following criteria:
        *   Their status is `SENT_TO_PROVIDER`.
        *   Their `updated_at` timestamp is within the last **72 hours** (to avoid querying old records).
    *   Group the resulting messages by their `provider`.
    *   For each provider group:
        *   Get the corresponding provider adapter.
        *   Check if `adapter.supports_status_check` is `True`. If not, skip to the next provider.
        *   If it is `True`, call the `adapter.check_status()` method with the list of `provider_message_id`s for that group.
        *   Based on the returned dictionary, update each corresponding `Message` object in the database:
            *   Update the `status` field to either `DELIVERED` or `FAILED`.
            *   If the status is `DELIVERED`, update the new `delivered_at` field with the timestamp received from the provider.

3.  **Schedule the Task:**
    *   In `server-b/sms_gateway_project/settings.py`, add the new `update_delivery_statuses` task to the `CELERY_BEAT_SCHEDULE`. Configure it to run periodically (e.g., every 5 minutes).

---

### **Phase 4: Update the User Interface**

Finally, update the Django templates to reflect the new status information.

1.  **Update the Message List Template:**
    *   Locate the message list template (`server-b/messaging/templates/messaging/message_list.html`).
    *   Modify the logic for the "Date Sent" column. It should now display the most recent relevant timestamp in this order of priority:
        1.  `delivered_at` (if available)
        2.  `sent_at` (if available)
        3.  `created_at` (as a fallback)

2.  **Implement New Status Styling:**
    *   In the CSS file (`server-b/static/css/dashboard.css`), add new style classes for the new message statuses. Use the following table as your guide. The color references are based on the Tailwind CSS color palette.

| Status | CSS Class Name | Background Color | Text Color | Border Color |
| :--- | :--- | :--- | :--- | :--- |
| `PENDING` | `pill--pending` | `bg-slate-100` | `text-slate-600` | `border-slate-200` |
| `PROCESSING` | `pill--processing`| `bg-blue-100` | `text-blue-700` | `border-blue-200` |
| `AWAITING_RETRY`| `pill--retry` | `bg-orange-100` | `text-orange-700`| `border-orange-200`|
| `SENT` | `pill--sent` | `bg-green-100` | `text-green-700` | `border-green-200` |
| `DELIVERED` | `pill--delivered` | `bg-emerald-100`| `text-emerald-800`| `border-emerald-300`|
| `FAILED`/`REJECTED`| `pill--off` | `bg-red-100` | `text-red-700` | `border-red-200` |

3.  **Apply Dynamic Classes in Template:**
    *   In the message list template (`message_list.html`), use Django template logic (`{% if %}` or a custom template tag) to dynamically apply the correct CSS class to the status pill element based on the `message.status` value.

4.  **Update the Message Detail View:**
    *   Locate the message detail template (`server-b/messaging/templates/messaging/message_detail.html`).
    *   Ensure it also displays the final status (`DELIVERED`/`FAILED`) using the new styling and shows the new delivery timestamp (`delivered_at`) if it exists.