// app/api/stations/route.ts
import { createClient } from '@/utils/supabase/server';
import { NextResponse } from 'next/server';

export async function GET() {
  const supabase = await createClient();

  // Fetch all stations from your table
  const { data, error } = await supabase
    .from('stations')
    .select('*'); // You can replace '*' with specific columns like 'id, station_name, city, latitude, longitude' for better performance

  if (error) {
    // Log the error for your own debugging, send a generic message to the frontend
    console.error('Supabase Error:', error);
    return NextResponse.json({ error: 'Failed to fetch stations' }, { status: 500 });
  }

  // Return the data as JSON
  return NextResponse.json(data);
}