export default function BouncingDots() {
  return (
    <div className="flex gap-[4px] items-center justify-center">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-[5px] h-[5px] rounded-full bg-accent animate-bounce-dot"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </div>
  )
}
