export interface CatalogModel {
  id: number
  name: string
  category: string
  collection: string
  colors: number
  sizes: number
  skus: number
  status: "active" | "draft"
  price: string
  img: string
  rating: number | null
  orders: number
}
