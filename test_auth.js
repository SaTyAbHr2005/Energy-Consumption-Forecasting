require('dotenv').config({ path: 'frontend/.env.local' });
const { createClient } = require('@supabase/supabase-js');
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
async function test() {
  const { data, error } = await supabase.auth.signInWithPassword({ email: 'user123@gmail.com', password: '12345678' });
  console.log('Error:', error?.message);
  console.log('Session:', !!data.session);
}
test();
