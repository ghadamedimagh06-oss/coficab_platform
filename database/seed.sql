-- CofICab Platform Seed Data

-- Insert Sample Users
INSERT INTO users (username, email, password_hash) VALUES
('admin', 'admin@coficab.com', 'hashed_password_here'),
('user1', 'user1@coficab.com', 'hashed_password_here');

-- Insert Sample Agents
INSERT INTO agents (name, agent_type, status) VALUES
('Watchdog Agent', 'watchdog', 'active'),
('Scheduler Agent', 'scheduler', 'active'),
('Alert Agent', 'alert', 'active'),
('Tracker Agent', 'tracker', 'active');

-- Insert Sample Events
INSERT INTO events (agent_id, event_type, description, severity) VALUES
((SELECT id FROM agents WHERE name = 'Watchdog Agent' LIMIT 1), 'file_change', 'File modified in /data/config', 'info'),
((SELECT id FROM agents WHERE name = 'Scheduler Agent' LIMIT 1), 'task_completed', 'Scheduled task executed successfully', 'info');

-- Insert Sample Tasks
INSERT INTO tasks (agent_id, title, description, status) VALUES
((SELECT id FROM agents WHERE name = 'Scheduler Agent' LIMIT 1), 'Backup Database', 'Nightly database backup', 'pending'),
((SELECT id FROM agents WHERE name = 'Tracker Agent' LIMIT 1), 'Track Changes', 'Monitor data changes', 'in_progress');
