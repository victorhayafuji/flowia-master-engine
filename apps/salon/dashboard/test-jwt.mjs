import { createClient } from '@supabase/supabase-js';
import fs from 'fs';
import path from 'path';
import ws from 'ws';

const envPath = path.resolve('../.env');
const envFile = fs.readFileSync(envPath, 'utf-8');
const env = {};
envFile.split('\n').forEach(line => {
  const match = line.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
  if (match) {
    env[match[1]] = match[2].replace(/(^['"]|['"]$)/g, '').trim();
  }
});

const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_KEY, {
  auth: { persistSession: false },
  realtime: { transport: ws }
});

async function run() {
  const { data } = await supabase.auth.signInWithPassword({
    email: 'admin2@flowia.com',
    password: 'password123'
  });
  const jwt = data.session.access_token;
  const payload = Buffer.from(jwt.split('.')[1], 'base64').toString();
  console.log(JSON.parse(payload));
}
run();
