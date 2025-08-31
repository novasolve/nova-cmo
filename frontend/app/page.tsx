import { redirect } from 'next/navigation';

export default function Home() {
  // Redirect to the new chat console
  redirect('/threads/default');
}


