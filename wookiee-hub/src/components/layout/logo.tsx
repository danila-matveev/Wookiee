import { Link } from "react-router-dom"

function Logo() {
  return (
    <Link
      to="/"
      data-slot="logo"
      className="flex items-center justify-center w-[34px] h-[34px] rounded-lg bg-gradient-to-br from-[#8B5CF6] to-[#EC4899] text-white font-bold text-sm shrink-0"
    >
      W
    </Link>
  )
}

export { Logo }
