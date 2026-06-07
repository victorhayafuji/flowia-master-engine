import { createClient } from '@supabase/supabase-js'
import dotenv from 'dotenv'

dotenv.config({ path: '.env' })

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_KEY
)

async function testAuth() {
  console.log("Testing auth...")
  const { data: authData, error: authErr } = await supabase.auth.signInWithPassword({
    email: 'admin2@flowia.com',
    password: 'password123'
  })
  
  if (authErr) {
    console.error("Auth Error:", authErr.message)
    return
  }
  console.log("Auth Success!")
  
  console.log("Fetching patients...")
  const { data, error } = await supabase.from('patients').select('*')
  
  if (error) {
    console.error("DB Error:", error)
  } else {
    console.log("Patients:", data)
  }
}

testAuth()
