import React from 'react';
import {
  listUsers,
  createUser,
  deleteUser,
  activateUser,
  deactivateUser,
  updateUser,
  User,
  UserCreate,
} from '../api/users';

export default function UsersAdmin() {
  const [users, setUsers] = React.useState<User[]>([]);
  const [form, setForm] = React.useState<UserCreate>({
    name: '',
    username: '',
    daily_quota: 0,
    api_key: '',
    password: '',
    note: '',
  });
  const [editingId, setEditingId] = React.useState<number | null>(null);
  const [editForm, setEditForm] = React.useState<Partial<User>>({});

  React.useEffect(() => {
    listUsers().then(setUsers);
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const u = await createUser(form);
    setUsers([...users, u]);
    setForm({ name: '', username: '', daily_quota: 0, api_key: '', password: '', note: '' });
  };

  const handleDelete = async (id: number) => {
    await deleteUser(id);
    setUsers(users.filter((u) => u.id !== id));
  };

  const handleToggle = async (user: User) => {
    const updated = user.active ? await deactivateUser(user.id) : await activateUser(user.id);
    setUsers(users.map((u) => (u.id === user.id ? updated : u)));
  };

  const startEdit = (user: User) => {
    setEditingId(user.id);
    setEditForm({ ...user });
  };

  const submitEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editingId === null) return;
    const updated = await updateUser(editingId, editForm);
    setUsers(users.map((u) => (u.id === updated.id ? updated : u)));
    setEditingId(null);
  };

  return (
    <div className="p-4 space-y-4">
      <form onSubmit={handleCreate} className="space-x-2">
        <input
          placeholder="Name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <input
          placeholder="Username"
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
        />
        <input
          placeholder="Daily Quota"
          type="number"
          value={form.daily_quota}
          onChange={(e) => setForm({ ...form, daily_quota: Number(e.target.value) })}
        />
        <input
          placeholder="API Key"
          value={form.api_key}
          onChange={(e) => setForm({ ...form, api_key: e.target.value })}
        />
        <input
          placeholder="Password"
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <input
          placeholder="Note"
          value={form.note || ''}
          onChange={(e) => setForm({ ...form, note: e.target.value })}
        />
        <button type="submit">Add User</button>
      </form>

      <table className="w-full border">
        <thead>
          <tr>
            <th>ID</th>
            <th>Username</th>
            <th>Name</th>
            <th>Active</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              {editingId === u.id ? (
                <>
                  <td>{u.id}</td>
                  <td>{u.username}</td>
                  <td>
                    <input
                      value={editForm.name || ''}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    />
                  </td>
                  <td>{u.active ? 'Yes' : 'No'}</td>
                  <td>
                    <button onClick={submitEdit}>Save</button>
                    <button onClick={() => setEditingId(null)}>Cancel</button>
                  </td>
                </>
              ) : (
                <>
                  <td>{u.id}</td>
                  <td>{u.username}</td>
                  <td>{u.name}</td>
                  <td>{u.active ? 'Yes' : 'No'}</td>
                  <td className="space-x-2">
                    <button onClick={() => startEdit(u)}>Edit</button>
                    <button onClick={() => handleToggle(u)}>
                      {u.active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button onClick={() => handleDelete(u.id)}>Delete</button>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
