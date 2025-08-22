# Frontend API Documentation

This document outlines the API endpoints used by the frontend application to interact with the backend services. All endpoints are relative to the `/api` base URL.

## Authentication

### 1. `POST /auth/login`

*   **Description**: Authenticates a user and returns a JWT token.
*   **Input**:
    *   `username` (string): The user's username.
    *   `password` (string): The user's password.
*   **Output**:
    *   `{ token: string }`: A JSON object containing the JWT token.

### 2. `POST /auth/logout`

*   **Description**: Logs out the current user by invalidating their session (if applicable on the backend).
*   **Input**: None (JWT token is sent via the `Authorization` header).
*   **Output**: None (successful logout is indicated by a 200 OK status).

## Dashboard

### 3. `GET /dashboard`

*   **Description**: Retrieves aggregated statistics for the SMS gateway dashboard.
*   **Input**: None.
*   **Output**:
    *   `{ total: number, sent: number, delivered: number, failed: number }`: An object containing various message statistics.

## Messages

### 4. `GET /messages`

*   **Description**: Retrieves a list of SMS messages, with optional filtering capabilities.
*   **Input**: (Query Parameters)
    *   `startDate` (string, optional): Filter messages sent after this date (e.g., 'YYYY-MM-DD').
    *   `endDate` (string, optional): Filter messages sent before this date (e.g., 'YYYY-MM-DD').
    *   `status` (string, optional): Filter messages by their status (e.g., 'sent', 'delivered', 'failed').
    *   `recipient` (string, optional): Filter messages by recipient phone number.
    *   `tracking_id` (string, optional): Filter messages by a specific tracking ID.
    *   `limit` (number, optional): Limit the number of results returned.
*   **Output**:
    *   `{ items: Array<Message>, total: number }`: An object containing an array of messages and the total count.
    *   `Message` object structure:
        *   `tracking_id` (string): Unique identifier for the message.
        *   `created_at` (string): Timestamp of when the message was created.
        *   `status` (string): Current status of the message (e.g., 'sent', 'delivered', 'failed').
        *   `recipient` (string): Recipient's phone number.
        *   `text` (string): The content of the SMS message.

### 5. `GET /messages/:trackingId`

*   **Description**: Retrieves detailed information for a single SMS message by its tracking ID.
*   **Input**:
    *   `trackingId` (string, URL parameter): The unique tracking ID of the message.
*   **Output**:
    *   `Message` object (same structure as described for `GET /messages`).

## User Management (Admin Only)

### 6. `GET /users`

*   **Description**: Retrieves a list of all users in the system. (Requires admin privileges).
*   **Input**: None.
*   **Output**:
    *   `Array<User>`: An array of user objects.
    *   `User` object structure:
        *   `id` (string): Unique identifier for the user.
        *   `username` (string): User's chosen username.
        *   `is_admin` (boolean): Indicates if the user has administrative privileges.
        *   `is_active` (boolean): Indicates if the user account is active.

### 7. `POST /users`

*   **Description**: Creates a new user account. (Requires admin privileges).
*   **Input**:
    *   `userData` (object):
        *   `username` (string): Desired username for the new user.
        *   `password` (string): Password for the new user.
        *   `is_admin` (boolean): Whether the new user should have admin privileges.
*   **Output**:
    *   `User` object (the newly created user, including its `id`).

### 8. `PUT /users/:userId`

*   **Description**: Updates an existing user's information. (Requires admin privileges).
*   **Input**:
    *   `userId` (string, URL parameter): The ID of the user to update.
    *   `userData` (object, optional):
        *   `username` (string, optional): New username.
        *   `password` (string, optional): New password.
        *   `is_admin` (boolean, optional): New admin status.
*   **Output**:
    *   `User` object (the updated user information).

### 9. `DELETE /users/:userId`

*   **Description**: Deletes a user account. (Requires admin privileges).
*   **Input**:
    *   `userId` (string, URL parameter): The ID of the user to delete.
*   **Output**: None (successful deletion is indicated by a 200 OK status).

### 10. `POST /users/:userId/activate`

*   **Description**: Activates a user account. (Requires admin privileges).
*   **Input**:
    *   `userId` (string, URL parameter): The ID of the user to activate.
*   **Output**: None (successful activation is indicated by a 200 OK status).

### 11. `POST /users/:userId/deactivate`

*   **Description**: Deactivates a user account. (Requires admin privileges).
*   **Input**:
    *   `userId` (string, URL parameter): The ID of the user to deactivate.
*   **Output**: None (successful deactivation is indicated by a 200 OK status).