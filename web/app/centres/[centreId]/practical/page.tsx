'use client';
import { useParams } from 'next/navigation';
import CentreEvidenceTabPage from '../../../components/CentreEvidenceTabPage';
export default function PracticalPage(){ const { centreId } = useParams<{centreId:string}>(); return <CentreEvidenceTabPage centreId={String(centreId)} kind="practical" />; }
