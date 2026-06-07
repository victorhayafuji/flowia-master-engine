import { createClient } from '@supabase/supabase-js';
import fs from 'fs';
import path from 'path';
import ws from 'ws';

// Parse .env manually
const envPath = path.resolve('../.env');
const envFile = fs.readFileSync(envPath, 'utf-8');
const env = {};
envFile.split('\n').forEach(line => {
  const match = line.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
  if (match) {
    let key = match[1];
    let value = match[2] || '';
    if (value.length > 0 && value.charAt(0) === '"' && value.charAt(value.length - 1) === '"') {
      value = value.replace(/\\n/gm, '\n');
    }
    env[key] = value.replace(/(^['"]|['"]$)/g, '').trim();
  }
});

const supabase = createClient(
  env.SUPABASE_URL,
  env.SUPABASE_KEY,
  {
    auth: { persistSession: false },
    realtime: {
      transport: ws
    }
  }
);

async function testAuth() {
  console.log("Testing auth...");
  const { data: authData, error: authErr } = await supabase.auth.signInWithPassword({
    email: 'admin2@flowia.com',
    password: 'password123'
  });
  
  if (authErr) {
    console.error("Auth Error:", authErr.message);
    return;
  }
  console.log("Auth Success! Session user id:", authData.user?.id);
  console.log("User metadata:", authData.user?.user_metadata);
  
  const { data: jwtData, error: jwtErr } = await supabase.rpc('debug_jwt');
  console.log("debug_jwt:", jwtData, jwtErr);

  console.log("Fetching patients...");
  const { data, error } = await supabase.from('patients').select('*').setHeader('Authorization', `Bearer ${authData.session.access_token}`);
  
  if (error) {
    console.error("DB Error:", error);
  } else {
    console.log(`Found ${data.length} patients.`);
    if (data.length > 0) {
      console.log("First patient:", data[0]);
    }
  }
}

testAuth();
