// ---------------------------------------------------------------------------
// Supply Order Form — dialog for creating a new supply order
// ---------------------------------------------------------------------------

import { useState } from "react"
import { useSupplyStore } from "@/stores/supply"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { generateNextOrderName } from "@/lib/supply-calc"
import { addDays, format } from "date-fns"

interface SupplyOrderFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SupplyOrderForm({ open, onOpenChange }: SupplyOrderFormProps) {
  const entity = useSupplyStore((s) => s.entity)
  const orders = useSupplyStore((s) => s.orders)
  const settings = useSupplyStore((s) => s.settings[s.entity])
  const createOrder = useSupplyStore((s) => s.createOrder)

  const generatedName = generateNextOrderName(entity, orders)
  const entityLabel = entity === "ooo" ? "ООО" : "ИП"

  const todayStr = format(new Date(), "yyyy-MM-dd")
  const defaultShipmentStr = format(
    addDays(new Date(), settings.default_lead_time_days),
    "yyyy-MM-dd",
  )
  const defaultDeliveryStr = format(
    addDays(new Date(), settings.default_lead_time_days + settings.default_transit_days),
    "yyyy-MM-dd",
  )

  const [orderDate, setOrderDate] = useState(todayStr)
  const [shipmentDate, setShipmentDate] = useState(defaultShipmentStr)
  const [deliveryDate, setDeliveryDate] = useState(defaultDeliveryStr)
  const [offsetDays, setOffsetDays] = useState(settings.default_offset_days)

  // Recalculate defaults when dialog opens
  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      const now = new Date()
      const nowStr = format(now, "yyyy-MM-dd")
      setOrderDate(nowStr)
      setShipmentDate(
        format(addDays(now, settings.default_lead_time_days), "yyyy-MM-dd"),
      )
      setDeliveryDate(
        format(
          addDays(now, settings.default_lead_time_days + settings.default_transit_days),
          "yyyy-MM-dd",
        ),
      )
      setOffsetDays(settings.default_offset_days)
    }
    onOpenChange(nextOpen)
  }

  // Auto-recalculate shipment when order date changes
  const handleOrderDateChange = (value: string) => {
    setOrderDate(value)
    if (value) {
      const base = new Date(value)
      const newShipment = addDays(base, settings.default_lead_time_days)
      const newShipmentStr = format(newShipment, "yyyy-MM-dd")
      setShipmentDate(newShipmentStr)
      setDeliveryDate(
        format(addDays(newShipment, settings.default_transit_days), "yyyy-MM-dd"),
      )
    }
  }

  // Auto-recalculate delivery when shipment date changes
  const handleShipmentDateChange = (value: string) => {
    setShipmentDate(value)
    if (value) {
      setDeliveryDate(
        format(addDays(new Date(value), settings.default_transit_days), "yyyy-MM-dd"),
      )
    }
  }

  const handleCreate = () => {
    const newOrder = createOrder(entity)

    // Patch dates and offset if user modified them
    const updateOrder = useSupplyStore.getState().updateOrder
    updateOrder(newOrder.id, {
      order_date: orderDate,
      shipment_date: shipmentDate,
      delivery_date: deliveryDate,
      offset_days: offsetDays,
    })

    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Новая поставка</DialogTitle>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Name — auto-generated, readonly */}
          <div className="grid grid-cols-[1fr_180px] items-center gap-4">
            <Label>Название</Label>
            <Input
              value={generatedName}
              readOnly
              className="text-sm text-muted-foreground bg-muted"
            />
          </div>

          {/* Entity — readonly */}
          <div className="grid grid-cols-[1fr_180px] items-center gap-4">
            <Label>Юрлицо</Label>
            <Input
              value={entityLabel}
              readOnly
              className="text-sm text-muted-foreground bg-muted"
            />
          </div>

          {/* Order date */}
          <div className="grid grid-cols-[1fr_180px] items-center gap-4">
            <Label htmlFor="order-date">Дата заказа</Label>
            <Input
              id="order-date"
              type="date"
              value={orderDate}
              onChange={(e) => handleOrderDateChange(e.target.value)}
            />
          </div>

          {/* Shipment date */}
          <div className="grid grid-cols-[1fr_180px] items-center gap-4">
            <Label htmlFor="shipment-date">Дата отправки</Label>
            <Input
              id="shipment-date"
              type="date"
              value={shipmentDate}
              onChange={(e) => handleShipmentDateChange(e.target.value)}
            />
          </div>

          {/* Delivery date */}
          <div className="grid grid-cols-[1fr_180px] items-center gap-4">
            <Label htmlFor="delivery-date">Дата доставки</Label>
            <Input
              id="delivery-date"
              type="date"
              value={deliveryDate}
              onChange={(e) => setDeliveryDate(e.target.value)}
            />
          </div>

          {/* Offset */}
          <div className="grid grid-cols-[1fr_180px] items-center gap-4">
            <Label htmlFor="offset-days">Смещение</Label>
            <Input
              id="offset-days"
              type="number"
              min={0}
              value={offsetDays}
              onChange={(e) => {
                const v = Number(e.target.value)
                if (!Number.isNaN(v)) setOffsetDays(v)
              }}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Отмена
          </Button>
          <Button onClick={handleCreate}>Создать</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
