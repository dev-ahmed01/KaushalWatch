export default function Loading() {
  return (
    <div aria-label="Loading view" aria-busy="true">
      <div className="h-8 w-48 rounded-lg kw-skeleton" />
      <div className="mt-3 h-4 w-80 max-w-full rounded kw-skeleton" />
      <div className="mt-8 grid gap-5 md:grid-cols-3">
        <div className="h-44 rounded-[18px] kw-skeleton" />
        <div className="h-44 rounded-[18px] kw-skeleton" />
        <div className="h-44 rounded-[18px] kw-skeleton" />
      </div>
    </div>
  );
}
