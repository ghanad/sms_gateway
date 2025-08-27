# Overall Goal: Establish a Single Source of Truth for User Identity
Implement an event-driven synchronization mechanism to ensure Server A has an up-to-date, in-memory cache of user configurations from Server B, including a stable user_id for every client. This ID will then be included in every message sent to Server B.

## Task 1: Enhance Server B to Broadcast Stable User IDs
This task makes Server B (the source of truth) responsible for publishing detailed configuration changes, including the immutable user.id.

### Sub-task 1.1: Define a New RabbitMQ Exchange for Configuration Sync
Establish a new, durable fanout exchange in RabbitMQ (e.g., config_events_exchange). This will be used exclusively for broadcasting configuration updates to any listening services.

### Sub-task 1.2: Enrich the User Configuration Sync Payload
Modify the logic that publishes user updates. The new JSON payload sent to RabbitMQ must now include the stable primary key: user.id.
The final payload should contain: api_key, user_id, username, is_active, and daily_quota.

### Sub-task 1.3: Implement Signal Handlers for Real-time Updates
Use Django signals (post_save on the User model, post_delete on the User model) to automatically trigger the publishing of an update or deletion event to the new exchange whenever a user is created, updated, or deleted.

### Sub-task 1.4: Create a "Full Sync" Management Command
Develop a Django management command (e.g., publish_all_users). When executed, this command will iterate through all users in the database and publish a user.updated event for each one. This is crucial for initializing or resynchronizing Server A's configuration cache after a restart or deployment.

## Task 2: Update Server A to Consume and Manage Enriched Configuration
This task makes Server A a consumer of the configuration events, allowing it to maintain an accurate, in-memory replica of user data.
Sub-task 2.1: Update In-Memory Data Models
Modify the Pydantic models used for configuration (ClientConfig) and authentication context (ClientContext) to include the new user_id field.

### Sub-task 2.2: Create a Background Configuration Consumer
Within Server A's application lifespan, launch a background asyncio task that:
Connects to RabbitMQ.
Declares an exclusive, temporary queue.
Binds this queue to the config_events_exchange.
Listens continuously for incoming messages (user.updated, user.deleted).

## Sub-task 2.3: Implement Logic to Update the In-Memory Cache
When the consumer receives a message, it must parse the payload and update the global, in-memory dictionary of client configurations.
For user.updated events: Add or update the client entry using the api_key as the dictionary key.
For user.deleted events: Remove the client entry from the dictionary.

## Sub-task 2.4: Modify Authentication Logic to Use the Cache
Change the authentication dependency (get_client_context) to look up the API-Key in the in-memory configuration cache instead of relying on environment variables. This function will now load the full ClientContext, including the stable user_id, into the request state.

## Task 3: Integrate the Stable User ID into the SMS Message Flow
This final task ensures the stable user_id is included in the operational message sent from Server A to Server B for processing.

## Sub-task 3.1: Modify the SMS Message Envelope Schema
Update the definition of the JSON message that is published to the sms_outbound_queue. It must now include the user_id field.

## Sub-task 3.2: Update the /api/v1/sms/send Endpoint
In the main API endpoint logic, after a client is successfully authenticated, retrieve the user_id from the ClientContext object (which is now available in the request state).

## Sub-task 3.3: Pass the User ID to the Publisher Function
Pass the retrieved user_id to the publish_sms_message function. This function will then place the user_id into the message envelope before publishing it to RabbitMQ for Server B to process.
