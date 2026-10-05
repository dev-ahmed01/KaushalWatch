'use client';
import { useParams } from 'next/navigation';
import CentreEvidenceTabPage from '../../../components/CentreEvidenceTabPage';
export default function AttendancePage(){ const { centreId } = useParams<{centreId:string}>(); return <CentreEvidenceTabPage centreId={String(centreId)} kind="attendance" />; }
