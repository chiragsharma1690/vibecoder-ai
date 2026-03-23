import React from 'react';
import { useAuth } from '../context/AuthContext';
import LogoutButton from '../components/LogoutButton';

const Dashboard = () => {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) {
    return <div>Redirecting...</div>;
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-4">Welcome, {user?.email}</h1>
      <p>This is the protected dashboard area.</p>
      <LogoutButton />
    </div>
  );
};

export default Dashboard;