import {NextRequest,NextResponse} from 'next/server';

/**
 * Deployment-only allowlist: an intentionally narrow public showcase, never
 * the local officer/demo API with unauthenticated case and messaging writes.
 */
export function proxy(request: NextRequest){
  if(process.env.NEXT_PUBLIC_KAUSHALWATCH_PUBLIC_SHOWCASE!=='true')return NextResponse.next();
  const pathname=request.nextUrl.pathname;
  const resource=pathname.startsWith('/_next/')
    || pathname==='/favicon.ico'
    || pathname==='/robots.txt'
    || /^\/camera-trust\/(training-bay|workshop-floor|east-corridor)\.mp4$/.test(pathname)
    || pathname==='/demo/studio'
    || pathname==='/api/demo/replay';
  if(resource){
    if(pathname==='/api/demo/replay' && request.method!=='GET'){
      return NextResponse.json({detail:'Read-only demo endpoint'},{status:405});
    }
    return NextResponse.next();
  }
  if(pathname.startsWith('/api/')){
    return NextResponse.json({detail:'Unavailable in the public synthetic showcase'},{status:404});
  }
  if(pathname==='/' || pathname.startsWith('/demo/') || !pathname.includes('.')){
    return NextResponse.redirect(new URL('/demo/studio',request.url));
  }
  return new NextResponse(null,{status:404});
}

export const config={matcher:['/((?!_next/static|_next/image).*)']};
