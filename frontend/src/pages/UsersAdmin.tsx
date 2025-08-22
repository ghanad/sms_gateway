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
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';

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
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    listUsers().then(setUsers);
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const u = await createUser(form);
    setUsers([...users, u]);
    setForm({ name: '', username: '', daily_quota: 0, api_key: '', password: '', note: '' });
    setOpen(false);
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
      <Button onClick={() => setOpen(true)}>Add User</Button>
      <Modal open={open} onClose={() => setOpen(false)} title="Add User">
        <form onSubmit={handleCreate} className="space-y-2">
          <Input
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Input
            placeholder="Username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
          />
          <Input
            placeholder="Daily Quota"
            type="number"
            value={form.daily_quota}
            onChange={(e) => setForm({ ...form, daily_quota: Number(e.target.value) })}
          />
          <Input
            placeholder="API Key"
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
          />
          <Input
            placeholder="Password"
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <Input
            placeholder="Note"
            value={form.note || ''}
            onChange={(e) => setForm({ ...form, note: e.target.value })}
          />
          <div className="flex justify-end space-x-2 pt-2">
            <Button type="submit">Save</Button>
            <Button type="button" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      </Modal>

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
                    <Input
                      value={editForm.name || ''}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    />
                  </td>
                  <td>{u.active ? 'Yes' : 'No'}</td>
                  <td>
                    <Button onClick={submitEdit}>Save</Button>
                    <Button onClick={() => setEditingId(null)}>Cancel</Button>
                  </td>
                </>
              ) : (
                <>
                  <td>{u.id}</td>
                  <td>{u.username}</td>
                  <td>{u.name}</td>
                  <td>{u.active ? 'Yes' : 'No'}</td>
                  <td className="space-x-2">
                    <Button onClick={() => startEdit(u)}>Edit</Button>
                    <Button onClick={() => handleToggle(u)}>
                      {u.active ? 'Deactivate' : 'Activate'}
                    </Button>
                    <Button onClick={() => handleDelete(u.id)}>Delete</Button>
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
