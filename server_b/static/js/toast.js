function showToast(message, type='info') {
  const toast = document.createElement('div');
  toast.className = `fixed top-4 right-4 bg-${type === 'error' ? 'red' : 'green'}-500 text-white px-4 py-2 rounded shadow`;
  toast.innerText = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}
window.showToast = showToast;
