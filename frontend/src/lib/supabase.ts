import { createClient } from '@supabase/supabase-js'
import { env } from '../config/env'

const supabaseUrl = env.supabaseUrl || 'https://tjtwdmhyvujarplllbee.supabase.co'
const supabaseAnonKey =
  env.supabaseAnonKey ||
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRqdHdkbWh5dnVqYXJwbGxsYmVlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMzNDc1OTMsImV4cCI6MjEwODkyMzU5M30.wiLVNHenFqg1-Gie0rP7AT0WYGqOlF2V-oTxRzlluwo'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
