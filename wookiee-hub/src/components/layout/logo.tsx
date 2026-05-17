import { Link } from "react-router-dom"

function Logo() {
  return (
    <Link
      to="/"
      data-slot="logo"
      className="flex items-center justify-center w-[34px] h-[34px] rounded-lg bg-stone-900 text-stone-50 dark:bg-stone-50 dark:text-stone-900 font-bold text-sm shrink-0"
    >
      W
    </Link>
  )
}

export { Logo }
