export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.1"
  }
  public: {
    Tables: {
      agent_registry: {
        Row: {
          agent_name: string
          agent_type: string
          changelog: string | null
          created_at: string | null
          created_by: string | null
          default_model: string | null
          description: string | null
          id: string
          is_active: boolean | null
          mcp_tools: string[] | null
          md_file_path: string | null
          model_tier: string | null
          prompt_hash: string
          system_prompt: string
          version: string
        }
        Insert: {
          agent_name: string
          agent_type: string
          changelog?: string | null
          created_at?: string | null
          created_by?: string | null
          default_model?: string | null
          description?: string | null
          id?: string
          is_active?: boolean | null
          mcp_tools?: string[] | null
          md_file_path?: string | null
          model_tier?: string | null
          prompt_hash: string
          system_prompt: string
          version: string
        }
        Update: {
          agent_name?: string
          agent_type?: string
          changelog?: string | null
          created_at?: string | null
          created_by?: string | null
          default_model?: string | null
          description?: string | null
          id?: string
          is_active?: boolean | null
          mcp_tools?: string[] | null
          md_file_path?: string | null
          model_tier?: string | null
          prompt_hash?: string
          system_prompt?: string
          version?: string
        }
        Relationships: []
      }
      artikuly: {
        Row: {
          artikul: string
          artikul_ozon: string | null
          created_at: string | null
          cvet_id: number | null
          id: number
          model_id: number | null
          nomenklatura_wb: number | null
          status_id: number | null
          updated_at: string | null
        }
        Insert: {
          artikul: string
          artikul_ozon?: string | null
          created_at?: string | null
          cvet_id?: number | null
          id?: number
          model_id?: number | null
          nomenklatura_wb?: number | null
          status_id?: number | null
          updated_at?: string | null
        }
        Update: {
          artikul?: string
          artikul_ozon?: string | null
          created_at?: string | null
          cvet_id?: number | null
          id?: number
          model_id?: number | null
          nomenklatura_wb?: number | null
          status_id?: number | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "artikuly_cvet_id_fkey"
            columns: ["cvet_id"]
            isOneToOne: false
            referencedRelation: "cveta"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "artikuly_cvet_id_fkey"
            columns: ["cvet_id"]
            isOneToOne: false
            referencedRelation: "v_cveta_modeli_osnova"
            referencedColumns: ["cvet_id"]
          },
          {
            foreignKeyName: "artikuly_cvet_id_fkey"
            columns: ["cvet_id"]
            isOneToOne: false
            referencedRelation: "v_statistika_cveta"
            referencedColumns: ["cvet_id"]
          },
          {
            foreignKeyName: "artikuly_model_id_fkey"
            columns: ["model_id"]
            isOneToOne: false
            referencedRelation: "modeli"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "artikuly_model_id_fkey"
            columns: ["model_id"]
            isOneToOne: false
            referencedRelation: "v_statistika_modeli"
            referencedColumns: ["model_id"]
          },
          {
            foreignKeyName: "artikuly_status_id_fkey"
            columns: ["status_id"]
            isOneToOne: false
            referencedRelation: "statusy"
            referencedColumns: ["id"]
          },
        ]
      }
      cveta: {
        Row: {
          color: string | null
          color_code: string
          created_at: string | null
          cvet: string | null
          hex: string | null
          id: number
          lastovica: string | null
          semeystvo: string | null
          semeystvo_id: number | null
          status_id: number | null
          updated_at: string | null
        }
        Insert: {
          color?: string | null
          color_code: string
          created_at?: string | null
          cvet?: string | null
          hex?: string | null
          id?: number
          lastovica?: string | null
          semeystvo?: string | null
          semeystvo_id?: number | null
          status_id?: number | null
          updated_at?: string | null
        }
        Update: {
          color?: string | null
          color_code?: string
          created_at?: string | null
          cvet?: string | null
          hex?: string | null
          id?: number
          lastovica?: string | null
          semeystvo?: string | null
          semeystvo_id?: number | null
          status_id?: number | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "cveta_semeystvo_id_fkey"
            columns: ["semeystvo_id"]
            isOneToOne: false
            referencedRelation: "semeystva_cvetov"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "cveta_status_id_fkey"
            columns: ["status_id"]
            isOneToOne: false
            referencedRelation: "statusy"
            referencedColumns: ["id"]
          },
        ]
      }
      fabriki: {
        Row: {
          email: string | null
          gorod: string | null
          id: number
          kontakt: string | null
          leadtime_dni: number | null
          nazvanie: string
          notes: string | null
          specializaciya: string | null
          strana: string | null
          wechat: string | null
        }
        Insert: {
          email?: string | null
          gorod?: string | null
          id?: number
          kontakt?: string | null
          leadtime_dni?: number | null
          nazvanie: string
          notes?: string | null
          specializaciya?: string | null
          strana?: string | null
          wechat?: string | null
        }
        Update: {
          email?: string | null
          gorod?: string | null
          id?: number
          kontakt?: string | null
          leadtime_dni?: number | null
          nazvanie?: string
          notes?: string | null
          specializaciya?: string | null
          strana?: string | null
          wechat?: string | null
        }
        Relationships: []
      }
      importery: {
        Row: {
          adres: string | null
          bank: string | null
          bik: string | null
          id: number
          inn: string | null
          kontakt: string | null
          kpp: string | null
          ks: string | null
          nazvanie: string
          nazvanie_en: string | null
          ogrn: string | null
          rs: string | null
          short_name: string | null
          telefon: string | null
        }
        Insert: {
          adres?: string | null
          bank?: string | null
          bik?: string | null
          id?: number
          inn?: string | null
          kontakt?: string | null
          kpp?: string | null
          ks?: string | null
          nazvanie: string
          nazvanie_en?: string | null
          ogrn?: string | null
          rs?: string | null
          short_name?: string | null
          telefon?: string | null
        }
        Update: {
          adres?: string | null
          bank?: string | null
          bik?: string | null
          id?: number
          inn?: string | null
          kontakt?: string | null
          kpp?: string | null
          ks?: string | null
          nazvanie?: string
          nazvanie_en?: string | null
          ogrn?: string | null
          rs?: string | null
          short_name?: string | null
          telefon?: string | null
        }
        Relationships: []
      }
      kanaly_prodazh: {
        Row: {
          active: boolean | null
          color: string | null
          id: number
          kod: string
          nazvanie: string
          poryadok: number | null
          short: string | null
        }
        Insert: {
          active?: boolean | null
          color?: string | null
          id?: number
          kod: string
          nazvanie: string
          poryadok?: number | null
          short?: string | null
        }
        Update: {
          active?: boolean | null
          color?: string | null
          id?: number
          kod?: string
          nazvanie?: string
          poryadok?: number | null
          short?: string | null
        }
        Relationships: []
      }
      kategorii: {
        Row: {
          id: number
          nazvanie: string
          opisanie: string | null
        }
        Insert: {
          id?: number
          nazvanie: string
          opisanie?: string | null
        }
        Update: {
          id?: number
          nazvanie?: string
          opisanie?: string | null
        }
        Relationships: []
      }
      kollekcii: {
        Row: {
          god_zapuska: number | null
          id: number
          nazvanie: string
          opisanie: string | null
        }
        Insert: {
          god_zapuska?: number | null
          id?: number
          nazvanie: string
          opisanie?: string | null
        }
        Update: {
          god_zapuska?: number | null
          id?: number
          nazvanie?: string
          opisanie?: string | null
        }
        Relationships: []
      }
      modeli: {
        Row: {
          artikul_modeli: string | null
          created_at: string | null
          id: number
          importer_id: number | null
          kod: string
          model_osnova_id: number | null
          nabor: boolean | null
          nazvanie: string
          nazvanie_en: string | null
          rossiyskiy_razmer: string | null
          status_id: number | null
          updated_at: string | null
        }
        Insert: {
          artikul_modeli?: string | null
          created_at?: string | null
          id?: number
          importer_id?: number | null
          kod: string
          model_osnova_id?: number | null
          nabor?: boolean | null
          nazvanie: string
          nazvanie_en?: string | null
          rossiyskiy_razmer?: string | null
          status_id?: number | null
          updated_at?: string | null
        }
        Update: {
          artikul_modeli?: string | null
          created_at?: string | null
          id?: number
          importer_id?: number | null
          kod?: string
          model_osnova_id?: number | null
          nabor?: boolean | null
          nazvanie?: string
          nazvanie_en?: string | null
          rossiyskiy_razmer?: string | null
          status_id?: number | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "modeli_importer_id_fkey"
            columns: ["importer_id"]
            isOneToOne: false
            referencedRelation: "importery"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "modeli_model_osnova_id_fkey"
            columns: ["model_osnova_id"]
            isOneToOne: false
            referencedRelation: "modeli_osnova"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "modeli_model_osnova_id_fkey"
            columns: ["model_osnova_id"]
            isOneToOne: false
            referencedRelation: "v_statistika_modeli_osnova"
            referencedColumns: ["osnova_id"]
          },
          {
            foreignKeyName: "modeli_status_id_fkey"
            columns: ["status_id"]
            isOneToOne: false
            referencedRelation: "statusy"
            referencedColumns: ["id"]
          },
        ]
      }
      modeli_osnova: {
        Row: {
          composition: string | null
          created_at: string | null
          description: string | null
          details: string | null
          dlina_cm: number | null
          dlya_kakoy_grudi: string | null
          fabrika_id: number | null
          forma_chashki: string | null
          gruppa_sertifikata: string | null
          id: number
          kategoriya_id: number | null
          kod: string
          kollekciya_id: number | null
          komplektaciya: string | null
          kratnost_koroba: number | null
          material: string | null
          naznachenie: string | null
          nazvanie_etiketka: string | null
          nazvanie_sayt: string | null
          notion_link: string | null
          notion_strategy_link: string | null
          opisanie_sayt: string | null
          po_nastroeniyu: string | null
          posadka_trusov: string | null
          razmery_modeli: string | null
          regulirovka: string | null
          shirina_cm: number | null
          sku_china: string | null
          sostav_syrya: string | null
          srok_proizvodstva: string | null
          status_id: number | null
          stepen_podderzhki: string | null
          stil: string | null
          tegi: string | null
          tip_kollekcii: string | null
          tnved: string | null
          upakovka: string | null
          upakovka_id: number | null
          updated_at: string | null
          ves_kg: number | null
          vid_trusov: string | null
          vysota_cm: number | null
          yandex_disk_link: string | null
          zastezhka: string | null
        }
        Insert: {
          composition?: string | null
          created_at?: string | null
          description?: string | null
          details?: string | null
          dlina_cm?: number | null
          dlya_kakoy_grudi?: string | null
          fabrika_id?: number | null
          forma_chashki?: string | null
          gruppa_sertifikata?: string | null
          id?: number
          kategoriya_id?: number | null
          kod: string
          kollekciya_id?: number | null
          komplektaciya?: string | null
          kratnost_koroba?: number | null
          material?: string | null
          naznachenie?: string | null
          nazvanie_etiketka?: string | null
          nazvanie_sayt?: string | null
          notion_link?: string | null
          notion_strategy_link?: string | null
          opisanie_sayt?: string | null
          po_nastroeniyu?: string | null
          posadka_trusov?: string | null
          razmery_modeli?: string | null
          regulirovka?: string | null
          shirina_cm?: number | null
          sku_china?: string | null
          sostav_syrya?: string | null
          srok_proizvodstva?: string | null
          status_id?: number | null
          stepen_podderzhki?: string | null
          stil?: string | null
          tegi?: string | null
          tip_kollekcii?: string | null
          tnved?: string | null
          upakovka?: string | null
          upakovka_id?: number | null
          updated_at?: string | null
          ves_kg?: number | null
          vid_trusov?: string | null
          vysota_cm?: number | null
          yandex_disk_link?: string | null
          zastezhka?: string | null
        }
        Update: {
          composition?: string | null
          created_at?: string | null
          description?: string | null
          details?: string | null
          dlina_cm?: number | null
          dlya_kakoy_grudi?: string | null
          fabrika_id?: number | null
          forma_chashki?: string | null
          gruppa_sertifikata?: string | null
          id?: number
          kategoriya_id?: number | null
          kod?: string
          kollekciya_id?: number | null
          komplektaciya?: string | null
          kratnost_koroba?: number | null
          material?: string | null
          naznachenie?: string | null
          nazvanie_etiketka?: string | null
          nazvanie_sayt?: string | null
          notion_link?: string | null
          notion_strategy_link?: string | null
          opisanie_sayt?: string | null
          po_nastroeniyu?: string | null
          posadka_trusov?: string | null
          razmery_modeli?: string | null
          regulirovka?: string | null
          shirina_cm?: number | null
          sku_china?: string | null
          sostav_syrya?: string | null
          srok_proizvodstva?: string | null
          status_id?: number | null
          stepen_podderzhki?: string | null
          stil?: string | null
          tegi?: string | null
          tip_kollekcii?: string | null
          tnved?: string | null
          upakovka?: string | null
          upakovka_id?: number | null
          updated_at?: string | null
          ves_kg?: number | null
          vid_trusov?: string | null
          vysota_cm?: number | null
          yandex_disk_link?: string | null
          zastezhka?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "modeli_osnova_fabrika_id_fkey"
            columns: ["fabrika_id"]
            isOneToOne: false
            referencedRelation: "fabriki"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "modeli_osnova_kategoriya_id_fkey"
            columns: ["kategoriya_id"]
            isOneToOne: false
            referencedRelation: "kategorii"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "modeli_osnova_kollekciya_id_fkey"
            columns: ["kollekciya_id"]
            isOneToOne: false
            referencedRelation: "kollekcii"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "modeli_osnova_status_id_fkey"
            columns: ["status_id"]
            isOneToOne: false
            referencedRelation: "statusy"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "modeli_osnova_upakovka_id_fkey"
            columns: ["upakovka_id"]
            isOneToOne: false
            referencedRelation: "upakovki"
            referencedColumns: ["id"]
          },
        ]
      }
      modeli_osnova_sertifikaty: {
        Row: {
          model_osnova_id: number
          sertifikat_id: number
        }
        Insert: {
          model_osnova_id: number
          sertifikat_id: number
        }
        Update: {
          model_osnova_id?: number
          sertifikat_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "modeli_osnova_sertifikaty_model_osnova_id_fkey"
            columns: ["model_osnova_id"]
            isOneToOne: false
            referencedRelation: "modeli_osnova"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "modeli_osnova_sertifikaty_model_osnova_id_fkey"
            columns: ["model_osnova_id"]
            isOneToOne: false
            referencedRelation: "v_statistika_modeli_osnova"
            referencedColumns: ["osnova_id"]
          },
          {
            foreignKeyName: "modeli_osnova_sertifikaty_sertifikat_id_fkey"
            columns: ["sertifikat_id"]
            isOneToOne: false
            referencedRelation: "sertifikaty"
            referencedColumns: ["id"]
          },
        ]
      }
      razmery: {
        Row: {
          china: string | null
          eu: string | null
          id: number
          nazvanie: string
          poryadok: number
          ru: string | null
        }
        Insert: {
          china?: string | null
          eu?: string | null
          id?: number
          nazvanie: string
          poryadok?: number
          ru?: string | null
        }
        Update: {
          china?: string | null
          eu?: string | null
          id?: number
          nazvanie?: string
          poryadok?: number
          ru?: string | null
        }
        Relationships: []
      }
      semeystva_cvetov: {
        Row: {
          id: number
          kod: string
          nazvanie: string
          opisanie: string | null
          poryadok: number | null
        }
        Insert: {
          id?: number
          kod: string
          nazvanie: string
          opisanie?: string | null
          poryadok?: number | null
        }
        Update: {
          id?: number
          kod?: string
          nazvanie?: string
          opisanie?: string | null
          poryadok?: number | null
        }
        Relationships: []
      }
      sertifikaty: {
        Row: {
          created_at: string | null
          data_okonchaniya: string | null
          data_vydachi: string | null
          file_url: string | null
          gruppa_sertifikata: string | null
          id: number
          nazvanie: string
          nomer: string | null
          organ_sertifikacii: string | null
          tip: string | null
          updated_at: string | null
        }
        Insert: {
          created_at?: string | null
          data_okonchaniya?: string | null
          data_vydachi?: string | null
          file_url?: string | null
          gruppa_sertifikata?: string | null
          id?: number
          nazvanie: string
          nomer?: string | null
          organ_sertifikacii?: string | null
          tip?: string | null
          updated_at?: string | null
        }
        Update: {
          created_at?: string | null
          data_okonchaniya?: string | null
          data_vydachi?: string | null
          file_url?: string | null
          gruppa_sertifikata?: string | null
          id?: number
          nazvanie?: string
          nomer?: string | null
          organ_sertifikacii?: string | null
          tip?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      skleyki_ozon: {
        Row: {
          created_at: string | null
          id: number
          importer_id: number | null
          nazvanie: string
          updated_at: string | null
        }
        Insert: {
          created_at?: string | null
          id?: number
          importer_id?: number | null
          nazvanie: string
          updated_at?: string | null
        }
        Update: {
          created_at?: string | null
          id?: number
          importer_id?: number | null
          nazvanie?: string
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "skleyki_ozon_importer_id_fkey"
            columns: ["importer_id"]
            isOneToOne: false
            referencedRelation: "importery"
            referencedColumns: ["id"]
          },
        ]
      }
      skleyki_wb: {
        Row: {
          created_at: string | null
          id: number
          importer_id: number | null
          nazvanie: string
          updated_at: string | null
        }
        Insert: {
          created_at?: string | null
          id?: number
          importer_id?: number | null
          nazvanie: string
          updated_at?: string | null
        }
        Update: {
          created_at?: string | null
          id?: number
          importer_id?: number | null
          nazvanie?: string
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "skleyki_wb_importer_id_fkey"
            columns: ["importer_id"]
            isOneToOne: false
            referencedRelation: "importery"
            referencedColumns: ["id"]
          },
        ]
      }
      statusy: {
        Row: {
          color: string | null
          id: number
          nazvanie: string
          tip: string
        }
        Insert: {
          color?: string | null
          id?: number
          nazvanie: string
          tip: string
        }
        Update: {
          color?: string | null
          id?: number
          nazvanie?: string
          tip?: string
        }
        Relationships: []
      }
      tg_chat_members: {
        Row: {
          chat_id: number
          joined_at: string
          left_at: string | null
          role: string
          telegram_id: number
        }
        Insert: {
          chat_id: number
          joined_at?: string
          left_at?: string | null
          role?: string
          telegram_id: number
        }
        Update: {
          chat_id?: number
          joined_at?: string
          left_at?: string | null
          role?: string
          telegram_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "tg_chat_members_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "tg_chats"
            referencedColumns: ["chat_id"]
          },
          {
            foreignKeyName: "tg_chat_members_telegram_id_fkey"
            columns: ["telegram_id"]
            isOneToOne: false
            referencedRelation: "tg_users"
            referencedColumns: ["telegram_id"]
          },
        ]
      }
      tg_chats: {
        Row: {
          ai_summary: string | null
          chat_id: number
          chat_type: string
          created_at: string
          is_active: boolean
          purpose: string | null
          summary_updated_at: string | null
          title: string
        }
        Insert: {
          ai_summary?: string | null
          chat_id: number
          chat_type?: string
          created_at?: string
          is_active?: boolean
          purpose?: string | null
          summary_updated_at?: string | null
          title: string
        }
        Update: {
          ai_summary?: string | null
          chat_id?: number
          chat_type?: string
          created_at?: string
          is_active?: boolean
          purpose?: string | null
          summary_updated_at?: string | null
          title?: string
        }
        Relationships: []
      }
      tg_messages: {
        Row: {
          attachment_type: string | null
          chat_id: number
          created_at: string
          has_attachment: boolean
          id: number
          message_id: number
          reply_to_message_id: number | null
          sent_at: string
          telegram_id: number
          text: string | null
        }
        Insert: {
          attachment_type?: string | null
          chat_id: number
          created_at?: string
          has_attachment?: boolean
          id?: number
          message_id: number
          reply_to_message_id?: number | null
          sent_at: string
          telegram_id: number
          text?: string | null
        }
        Update: {
          attachment_type?: string | null
          chat_id?: number
          created_at?: string
          has_attachment?: boolean
          id?: number
          message_id?: number
          reply_to_message_id?: number | null
          sent_at?: string
          telegram_id?: number
          text?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "tg_messages_chat_id_fkey"
            columns: ["chat_id"]
            isOneToOne: false
            referencedRelation: "tg_chats"
            referencedColumns: ["chat_id"]
          },
          {
            foreignKeyName: "tg_messages_telegram_id_fkey"
            columns: ["telegram_id"]
            isOneToOne: false
            referencedRelation: "tg_users"
            referencedColumns: ["telegram_id"]
          },
        ]
      }
      tg_users: {
        Row: {
          ai_profile: string | null
          bitrix_user_id: number | null
          created_at: string
          first_name: string
          is_team: boolean
          last_name: string | null
          profile_updated_at: string | null
          role_in_company: string | null
          telegram_id: number
          username: string | null
        }
        Insert: {
          ai_profile?: string | null
          bitrix_user_id?: number | null
          created_at?: string
          first_name?: string
          is_team?: boolean
          last_name?: string | null
          profile_updated_at?: string | null
          role_in_company?: string | null
          telegram_id: number
          username?: string | null
        }
        Update: {
          ai_profile?: string | null
          bitrix_user_id?: number | null
          created_at?: string
          first_name?: string
          is_team?: boolean
          last_name?: string | null
          profile_updated_at?: string | null
          role_in_company?: string | null
          telegram_id?: number
          username?: string | null
        }
        Relationships: []
      }
      tool_runs: {
        Row: {
          depth: string | null
          details: Json | null
          duration_sec: number | null
          environment: string | null
          error_message: string | null
          error_stage: string | null
          finished_at: string | null
          id: string
          items_processed: number | null
          model_used: string | null
          notes: string | null
          output_sections: number | null
          period_end: string | null
          period_start: string | null
          result_url: string | null
          started_at: string | null
          status: string
          tokens_input: number | null
          tokens_output: number | null
          tool_slug: string
          tool_version: string | null
          trigger_type: string | null
          triggered_by: string | null
        }
        Insert: {
          depth?: string | null
          details?: Json | null
          duration_sec?: number | null
          environment?: string | null
          error_message?: string | null
          error_stage?: string | null
          finished_at?: string | null
          id?: string
          items_processed?: number | null
          model_used?: string | null
          notes?: string | null
          output_sections?: number | null
          period_end?: string | null
          period_start?: string | null
          result_url?: string | null
          started_at?: string | null
          status: string
          tokens_input?: number | null
          tokens_output?: number | null
          tool_slug: string
          tool_version?: string | null
          trigger_type?: string | null
          triggered_by?: string | null
        }
        Update: {
          depth?: string | null
          details?: Json | null
          duration_sec?: number | null
          environment?: string | null
          error_message?: string | null
          error_stage?: string | null
          finished_at?: string | null
          id?: string
          items_processed?: number | null
          model_used?: string | null
          notes?: string | null
          output_sections?: number | null
          period_end?: string | null
          period_start?: string | null
          result_url?: string | null
          started_at?: string | null
          status?: string
          tokens_input?: number | null
          tokens_output?: number | null
          tool_slug?: string
          tool_version?: string | null
          trigger_type?: string | null
          triggered_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "tool_runs_tool_slug_fkey"
            columns: ["tool_slug"]
            isOneToOne: false
            referencedRelation: "tools"
            referencedColumns: ["slug"]
          },
        ]
      }
      tools: {
        Row: {
          available_in_claude_code: boolean
          available_in_codex: boolean
          avg_duration: number | null
          category: string | null
          created_at: string | null
          data_sources: string[] | null
          depends_on: string[] | null
          description: string | null
          display_name: string
          doc_url: string | null
          health_check: string | null
          how_it_works: string | null
          id: string
          is_platform: boolean
          last_run_at: string | null
          last_status: string | null
          name_ru: string | null
          output_description: string | null
          output_targets: string[] | null
          owner: string | null
          required_env_vars: string[] | null
          run_command: string | null
          show_in_hub: boolean
          skill_md_path: string | null
          slug: string
          status: string | null
          success_rate: number | null
          total_runs: number | null
          type: string
          updated_at: string | null
          usage_examples: string | null
          version: string | null
        }
        Insert: {
          available_in_claude_code?: boolean
          available_in_codex?: boolean
          avg_duration?: number | null
          category?: string | null
          created_at?: string | null
          data_sources?: string[] | null
          depends_on?: string[] | null
          description?: string | null
          display_name: string
          doc_url?: string | null
          health_check?: string | null
          how_it_works?: string | null
          id?: string
          is_platform?: boolean
          last_run_at?: string | null
          last_status?: string | null
          name_ru?: string | null
          output_description?: string | null
          output_targets?: string[] | null
          owner?: string | null
          required_env_vars?: string[] | null
          run_command?: string | null
          show_in_hub?: boolean
          skill_md_path?: string | null
          slug: string
          status?: string | null
          success_rate?: number | null
          total_runs?: number | null
          type: string
          updated_at?: string | null
          usage_examples?: string | null
          version?: string | null
        }
        Update: {
          available_in_claude_code?: boolean
          available_in_codex?: boolean
          avg_duration?: number | null
          category?: string | null
          created_at?: string | null
          data_sources?: string[] | null
          depends_on?: string[] | null
          description?: string | null
          display_name?: string
          doc_url?: string | null
          health_check?: string | null
          how_it_works?: string | null
          id?: string
          is_platform?: boolean
          last_run_at?: string | null
          last_status?: string | null
          name_ru?: string | null
          output_description?: string | null
          output_targets?: string[] | null
          owner?: string | null
          required_env_vars?: string[] | null
          run_command?: string | null
          show_in_hub?: boolean
          skill_md_path?: string | null
          slug?: string
          status?: string | null
          success_rate?: number | null
          total_runs?: number | null
          type?: string
          updated_at?: string | null
          usage_examples?: string | null
          version?: string | null
        }
        Relationships: []
      }
      tovary: {
        Row: {
          artikul_id: number | null
          barkod: string
          barkod_gs1: string | null
          barkod_gs2: string | null
          barkod_perehod: string | null
          created_at: string | null
          id: number
          lamoda_seller_sku: string | null
          ozon_fbo_sku_id: number | null
          ozon_product_id: number | null
          razmer_id: number | null
          sku_china_size: string | null
          status_id: number | null
          status_lamoda_id: number | null
          status_ozon_id: number | null
          status_sayt_id: number | null
          updated_at: string | null
        }
        Insert: {
          artikul_id?: number | null
          barkod: string
          barkod_gs1?: string | null
          barkod_gs2?: string | null
          barkod_perehod?: string | null
          created_at?: string | null
          id?: number
          lamoda_seller_sku?: string | null
          ozon_fbo_sku_id?: number | null
          ozon_product_id?: number | null
          razmer_id?: number | null
          sku_china_size?: string | null
          status_id?: number | null
          status_lamoda_id?: number | null
          status_ozon_id?: number | null
          status_sayt_id?: number | null
          updated_at?: string | null
        }
        Update: {
          artikul_id?: number | null
          barkod?: string
          barkod_gs1?: string | null
          barkod_gs2?: string | null
          barkod_perehod?: string | null
          created_at?: string | null
          id?: number
          lamoda_seller_sku?: string | null
          ozon_fbo_sku_id?: number | null
          ozon_product_id?: number | null
          razmer_id?: number | null
          sku_china_size?: string | null
          status_id?: number | null
          status_lamoda_id?: number | null
          status_ozon_id?: number | null
          status_sayt_id?: number | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "tovary_artikul_id_fkey"
            columns: ["artikul_id"]
            isOneToOne: false
            referencedRelation: "artikuly"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tovary_razmer_id_fkey"
            columns: ["razmer_id"]
            isOneToOne: false
            referencedRelation: "razmery"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tovary_status_id_fkey"
            columns: ["status_id"]
            isOneToOne: false
            referencedRelation: "statusy"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tovary_status_lamoda_id_fkey"
            columns: ["status_lamoda_id"]
            isOneToOne: false
            referencedRelation: "statusy"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tovary_status_ozon_id_fkey"
            columns: ["status_ozon_id"]
            isOneToOne: false
            referencedRelation: "statusy"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tovary_status_sayt_id_fkey"
            columns: ["status_sayt_id"]
            isOneToOne: false
            referencedRelation: "statusy"
            referencedColumns: ["id"]
          },
        ]
      }
      tovary_skleyki_ozon: {
        Row: {
          skleyka_id: number
          tovar_id: number
        }
        Insert: {
          skleyka_id: number
          tovar_id: number
        }
        Update: {
          skleyka_id?: number
          tovar_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "tovary_skleyki_ozon_skleyka_id_fkey"
            columns: ["skleyka_id"]
            isOneToOne: false
            referencedRelation: "skleyki_ozon"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tovary_skleyki_ozon_tovar_id_fkey"
            columns: ["tovar_id"]
            isOneToOne: false
            referencedRelation: "tovary"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tovary_skleyki_ozon_tovar_id_fkey"
            columns: ["tovar_id"]
            isOneToOne: false
            referencedRelation: "v_tovary_polnaya_info"
            referencedColumns: ["tovar_id"]
          },
        ]
      }
      tovary_skleyki_wb: {
        Row: {
          skleyka_id: number
          tovar_id: number
        }
        Insert: {
          skleyka_id: number
          tovar_id: number
        }
        Update: {
          skleyka_id?: number
          tovar_id?: number
        }
        Relationships: [
          {
            foreignKeyName: "tovary_skleyki_wb_skleyka_id_fkey"
            columns: ["skleyka_id"]
            isOneToOne: false
            referencedRelation: "skleyki_wb"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tovary_skleyki_wb_tovar_id_fkey"
            columns: ["tovar_id"]
            isOneToOne: false
            referencedRelation: "tovary"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tovary_skleyki_wb_tovar_id_fkey"
            columns: ["tovar_id"]
            isOneToOne: false
            referencedRelation: "v_tovary_polnaya_info"
            referencedColumns: ["tovar_id"]
          },
        ]
      }
      ui_preferences: {
        Row: {
          id: number
          key: string
          scope: string
          updated_at: string | null
          value: Json | null
        }
        Insert: {
          id?: number
          key: string
          scope: string
          updated_at?: string | null
          value?: Json | null
        }
        Update: {
          id?: number
          key?: string
          scope?: string
          updated_at?: string | null
          value?: Json | null
        }
        Relationships: []
      }
      upakovki: {
        Row: {
          dlina_cm: number | null
          file_link: string | null
          id: number
          nazvanie: string
          notes: string | null
          obem_l: number | null
          poryadok: number | null
          price_yuan: number | null
          shirina_cm: number | null
          srok_izgotovleniya_dni: number | null
          tip: string | null
          vysota_cm: number | null
        }
        Insert: {
          dlina_cm?: number | null
          file_link?: string | null
          id?: number
          nazvanie: string
          notes?: string | null
          obem_l?: number | null
          poryadok?: number | null
          price_yuan?: number | null
          shirina_cm?: number | null
          srok_izgotovleniya_dni?: number | null
          tip?: string | null
          vysota_cm?: number | null
        }
        Update: {
          dlina_cm?: number | null
          file_link?: string | null
          id?: number
          nazvanie?: string
          notes?: string | null
          obem_l?: number | null
          poryadok?: number | null
          price_yuan?: number | null
          shirina_cm?: number | null
          srok_izgotovleniya_dni?: number | null
          tip?: string | null
          vysota_cm?: number | null
        }
        Relationships: []
      }
      wb_coeff_table: {
        Row: {
          id: number
          krp_pct: number
          ktr: number
          max_loc: number
          min_loc: number
          valid_from: string
        }
        Insert: {
          id?: number
          krp_pct: number
          ktr: number
          max_loc: number
          min_loc: number
          valid_from: string
        }
        Update: {
          id?: number
          krp_pct?: number
          ktr?: number
          max_loc?: number
          min_loc?: number
          valid_from?: string
        }
        Relationships: []
      }
      wb_tariffs: {
        Row: {
          acceptance: number
          created_at: string
          delivery_coef: number
          dt: string
          geo_name: string
          id: number
          logistics_1l: number
          logistics_extra_l: number
          storage_1l_day: number
          storage_coef: number
          warehouse_name: string
        }
        Insert: {
          acceptance?: number
          created_at?: string
          delivery_coef?: number
          dt: string
          geo_name?: string
          id?: number
          logistics_1l?: number
          logistics_extra_l?: number
          storage_1l_day?: number
          storage_coef?: number
          warehouse_name: string
        }
        Update: {
          acceptance?: number
          created_at?: string
          delivery_coef?: number
          dt?: string
          geo_name?: string
          id?: number
          logistics_1l?: number
          logistics_extra_l?: number
          storage_1l_day?: number
          storage_coef?: number
          warehouse_name?: string
        }
        Relationships: []
      }
    }
    Views: {
      agent_runs: {
        Row: {
          agent_name: string | null
          agent_type: string | null
          agent_version: string | null
          artifact: Json | null
          completion_tokens: number | null
          cost_usd: number | null
          created_at: string | null
          duration_ms: number | null
          error_message: string | null
          finished_at: string | null
          id: string | null
          llm_calls: number | null
          model: string | null
          output_summary: string | null
          parent_run_id: string | null
          prompt_tokens: number | null
          run_id: string | null
          started_at: string | null
          status: string | null
          system_prompt_hash: string | null
          task_type: string | null
          tool_calls: number | null
          total_tokens: number | null
          trigger: string | null
          user_input: string | null
        }
        Insert: {
          agent_name?: string | null
          agent_type?: string | null
          agent_version?: string | null
          artifact?: Json | null
          completion_tokens?: number | null
          cost_usd?: number | null
          created_at?: string | null
          duration_ms?: number | null
          error_message?: string | null
          finished_at?: string | null
          id?: string | null
          llm_calls?: number | null
          model?: string | null
          output_summary?: string | null
          parent_run_id?: string | null
          prompt_tokens?: number | null
          run_id?: string | null
          started_at?: string | null
          status?: string | null
          system_prompt_hash?: string | null
          task_type?: string | null
          tool_calls?: number | null
          total_tokens?: number | null
          trigger?: string | null
          user_input?: string | null
        }
        Update: {
          agent_name?: string | null
          agent_type?: string | null
          agent_version?: string | null
          artifact?: Json | null
          completion_tokens?: number | null
          cost_usd?: number | null
          created_at?: string | null
          duration_ms?: number | null
          error_message?: string | null
          finished_at?: string | null
          id?: string | null
          llm_calls?: number | null
          model?: string | null
          output_summary?: string | null
          parent_run_id?: string | null
          prompt_tokens?: number | null
          run_id?: string | null
          started_at?: string | null
          status?: string | null
          system_prompt_hash?: string | null
          task_type?: string | null
          tool_calls?: number | null
          total_tokens?: number | null
          trigger?: string | null
          user_input?: string | null
        }
        Relationships: []
      }
      v_artikuly_po_cvetam: {
        Row: {
          artikul: string | null
          color_code: string | null
          cvet: string | null
          kolichestvo_sku: number | null
          model: string | null
          model_nazvanie: string | null
          model_osnova: string | null
          nomenklatura_wb: number | null
          status_artikula: string | null
        }
        Relationships: []
      }
      v_cveta_modeli_osnova: {
        Row: {
          color_code: string | null
          cvet: string | null
          cvet_en: string | null
          cvet_id: number | null
          kolichestvo_artikulov: number | null
          kolichestvo_modeley: number | null
          kolichestvo_sku: number | null
          modeli_osnova: string | null
          status_cveta: string | null
        }
        Relationships: []
      }
      v_matrica_cveta_modeli: {
        Row: {
          Alice: string | null
          Audrey: string | null
          color_code: string | null
          cvet: string | null
          Joy: string | null
          Moon: string | null
          Ruby: string | null
          SetMoon: string | null
          SetRuby: string | null
          SetVuki: string | null
          Space: string | null
          Vuki: string | null
          Wendy: string | null
        }
        Relationships: []
      }
      v_modeli_po_osnove: {
        Row: {
          artikul_modeli: string | null
          importer: string | null
          model_kod: string | null
          model_nazvanie: string | null
          osnova: string | null
          status: string | null
        }
        Relationships: []
      }
      v_statistika_cveta: {
        Row: {
          color_code: string | null
          cvet: string | null
          cvet_en: string | null
          cvet_id: number | null
          kolichestvo_artikulov: number | null
          kolichestvo_modeley: number | null
          kolichestvo_tovarov: number | null
        }
        Relationships: []
      }
      v_statistika_modeli: {
        Row: {
          importer: string | null
          kod: string | null
          kolichestvo_artikulov: number | null
          kolichestvo_cvetov: number | null
          kolichestvo_tovarov: number | null
          model_id: number | null
          model_osnova: string | null
          nazvanie: string | null
          status: string | null
        }
        Relationships: []
      }
      v_statistika_modeli_osnova: {
        Row: {
          kategoriya: string | null
          kolichestvo_artikulov: number | null
          kolichestvo_tovarov: number | null
          kolichestvo_variaciy: number | null
          kollekciya: string | null
          osnova: string | null
          osnova_id: number | null
        }
        Relationships: []
      }
      v_tovary_polnaya_info: {
        Row: {
          artikul: string | null
          barkod: string | null
          barkod_gs1: string | null
          barkod_gs2: string | null
          color_code: string | null
          cvet: string | null
          cvet_en: string | null
          importer: string | null
          kategoriya: string | null
          kollekciya: string | null
          material: string | null
          model_kod: string | null
          model_nazvanie: string | null
          model_osnova: string | null
          nomenklatura_wb: number | null
          ozon_fbo_sku_id: number | null
          ozon_product_id: number | null
          razmer: string | null
          sostav_syrya: string | null
          status_tovara: string | null
          tovar_id: number | null
        }
        Relationships: []
      }
      v_tricot_nepolnye_cveta: {
        Row: {
          color_code: string | null
          cvet: string | null
          Joy: string | null
          Moon: string | null
          Ruby: string | null
          sostoyanie: string | null
          vsego_modeley: number | null
          Vuki: string | null
        }
        Relationships: []
      }
    }
    Functions: {
      get_istoriya_zapisi: {
        Args: { p_tablica: string; p_zapis_id: number }
        Returns: {
          data_izmeneniya: string
          novoe_znachenie: string
          pole: string
          polzovatel: string
          staroe_znachenie: string
          tip_operacii: string
        }[]
      }
      get_izmeneniya_za_period: {
        Args: { p_data_do?: string; p_data_ot: string }
        Returns: {
          data_izmeneniya: string
          novoe_znachenie: string
          pole: string
          polzovatel: string
          staroe_znachenie: string
          tablica: string
          tip_operacii: string
          zapis_id: number
        }[]
      }
      search_content: {
        Args: {
          filter_category?: string
          filter_color?: string
          filter_model?: string
          filter_sku?: string
          match_count?: number
          min_similarity?: number
          query_embedding: string
        }
        Returns: {
          color: string
          content_category: string
          disk_path: string
          file_name: string
          file_size: number
          id: number
          mime_type: string
          model_name: string
          similarity: number
          sku: string
        }[]
      }
      search_kb:
        | {
            Args: {
              filter_content_type?: string
              filter_module?: string
              match_count?: number
              min_similarity?: number
              query_embedding: string
            }
            Returns: {
              chunk_index: number
              content: string
              content_type: string
              file_name: string
              file_type: string
              id: number
              module: string
              similarity: number
              source_path: string
            }[]
          }
        | {
            Args: {
              filter_content_type?: string
              filter_module?: string
              filter_source_tag?: string
              match_count?: number
              min_similarity?: number
              query_embedding: string
            }
            Returns: {
              chunk_index: number
              content: string
              content_type: string
              file_name: string
              file_type: string
              id: number
              module: string
              similarity: number
              source_path: string
              source_tag: string
              verified: boolean
            }[]
          }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
