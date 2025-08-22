import React, { useEffect, useState } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import { Button, Modal, Box, TextField, FormControlLabel, Checkbox } from '@mui/material';
import apiService from '../../services/apiService.js';

const style = {
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  width: 400,
  bgcolor: 'background.paper',
  p: 4
};

const UserManagementPage = () => {
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [username, setUsername] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [extension, setExtension] = useState('');
  const [department, setDepartment] = useState('');
  const [password, setPassword] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [dailyQuota, setDailyQuota] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [isActive, setIsActive] = useState(true);

  const fetchUsers = async () => {
    const data = await apiService.getUsers();
    const formatted = data.map((u) => ({
      id: u.ID,
      username: u.Username,
      name: u.Name,
      phone: u.Phone,
      extension: u.Extension,
      department: u.Department,
      api_key: u.APIKey,
      daily_quota: u.DailyQuota,
      is_admin: u.IsAdmin,
      is_active: u.IsActive
    }));
    setUsers(formatted);
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const resetForm = () => {
    setUsername('');
    setName('');
    setPhone('');
    setExtension('');
    setDepartment('');
    setPassword('');
    setApiKey('');
    setDailyQuota('');
    setIsAdmin(false);
    setIsActive(true);
  };

  const handleOpenCreate = () => {
    setEditingId(null);
    resetForm();
    setOpen(true);
  };

  const handleOpenEdit = (user) => {
    setEditingId(user.id);
    setUsername(user.username);
    setName(user.name);
    setPhone(user.phone);
    setExtension(user.extension);
    setDepartment(user.department);
    setPassword('');
    setApiKey(user.api_key);
    setDailyQuota(user.daily_quota);
    setIsAdmin(user.is_admin);
    setIsActive(user.is_active);
    setOpen(true);
  };

  const handleSave = async () => {
    const payload = {
      username,
      name,
      phone,
      extension,
      department,
      password,
      api_key: apiKey,
      daily_quota: dailyQuota,
      is_admin: isAdmin,
      is_active: isActive
    };
    if (editingId) {
      await apiService.updateUser(editingId, payload);
    } else {
      await apiService.createUser(payload);
    }
    setOpen(false);
    resetForm();
    setEditingId(null);
    fetchUsers();
  };

  const handleDelete = async (id) => {
    await apiService.deleteUser(id);
    fetchUsers();
  };

  const handleToggleActive = async (user) => {
    if (user.is_active) {
      await apiService.deactivateUser(user.id);
    } else {
      await apiService.activateUser(user.id);
    }
    fetchUsers();
  };

  const columns = [
    { field: 'username', headerName: 'Username', flex: 1 },
    { field: 'name', headerName: 'Name', flex: 1 },
    { field: 'phone', headerName: 'Phone', flex: 1 },
    { field: 'extension', headerName: 'Extension', flex: 1 },
    { field: 'department', headerName: 'Department', flex: 1 },
    { field: 'api_key', headerName: 'API Key', flex: 1 },
    { field: 'daily_quota', headerName: 'Daily Quota', flex: 1 },
    { field: 'is_admin', headerName: 'Admin', flex: 0.5 },
    { field: 'is_active', headerName: 'Active', flex: 0.5 },
    {
      field: 'actions',
      headerName: 'Actions',
      flex: 1,
      renderCell: (params) => (
        <>
          <Button onClick={() => handleOpenEdit(params.row)} size="small">Edit</Button>
          <Button onClick={() => handleToggleActive(params.row)} size="small">
            {params.row.is_active ? 'Deactivate' : 'Activate'}
          </Button>
          <Button onClick={() => handleDelete(params.row.id)} size="small" color="error">Delete</Button>
        </>
      )
    }
  ];

  return (
    <div style={{ height: 500, width: '100%' }}>
      <Button variant="contained" sx={{ mb: 2 }} onClick={handleOpenCreate}>
        Create New User
      </Button>
      <DataGrid rows={users} columns={columns} getRowId={(row) => row.id} />
      <Modal open={open} onClose={() => setOpen(false)}>
        <Box sx={style}>
          <TextField label="Username" fullWidth margin="normal" value={username} onChange={(e) => setUsername(e.target.value)} />
          <TextField label="Name" fullWidth margin="normal" value={name} onChange={(e) => setName(e.target.value)} />
          <TextField label="Phone" fullWidth margin="normal" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <TextField label="Extension" fullWidth margin="normal" value={extension} onChange={(e) => setExtension(e.target.value)} />
          <TextField label="Department" fullWidth margin="normal" value={department} onChange={(e) => setDepartment(e.target.value)} />
          <TextField label="Password" type="password" fullWidth margin="normal" value={password} onChange={(e) => setPassword(e.target.value)} />
          <TextField label="API Key" fullWidth margin="normal" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          <TextField label="Daily Quota" fullWidth margin="normal" value={dailyQuota} onChange={(e) => setDailyQuota(e.target.value)} />
          <FormControlLabel control={<Checkbox checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />} label="Admin" />
          <FormControlLabel control={<Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />} label="Active" />
          <Button variant="contained" onClick={handleSave}>Save</Button>
        </Box>
      </Modal>
    </div>
  );
};

export default UserManagementPage;
