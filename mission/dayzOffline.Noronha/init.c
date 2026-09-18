void main()
{
    // INIT ECONOMY
    Hive ce = CreateHive();
    if ( ce )
        ce.InitOffline();

    // DATE RESET (Verão Fixo em Noronha)
    int year, month, day, hour, minute;
    int reset_month = 1, reset_day = 15;
    GetGame().GetWorld().GetDate(year, month, day, hour, minute);

    if ((month == reset_month) && (day < reset_day))
    {
        GetGame().GetWorld().SetDate(year, reset_month, reset_day, hour, minute);
    }
    else if ((month == reset_month + 1) && (day > reset_day))
    {
        GetGame().GetWorld().SetDate(year, reset_month, reset_day, hour, minute);
    }
    else if ((month < reset_month) || (month > reset_month + 1))
    {
        GetGame().GetWorld().SetDate(year, reset_month, reset_day, hour, minute);
    }
}

class CustomMission: MissionServer
{
    void SetRandomHealth(EntityAI itemEnt)
    {
        if ( itemEnt )
        {
            float rndHlt = Math.RandomFloat( 0.45, 0.65 );
            itemEnt.SetHealth01( "", "", rndHlt );
        }
    }

    override PlayerBase CreateCharacter(PlayerIdentity identity, vector pos, ParamsReadContext ctx, string characterName)
    {
        Entity playerEnt;
        playerEnt = GetGame().CreatePlayer( identity, characterName, pos, 0, "NONE" );
        Class.CastTo( m_player, playerEnt );
        GetGame().SelectPlayer( identity, m_player );

        return m_player;
    }

    override void StartingEquipSetup(PlayerBase player, bool clothesChosen)
    {
        EntityAI itemClothing;
        EntityAI itemEnt;

        // --- 1. ROUPAS E CHANCE DE CAMISA DE TIME ---
        itemClothing = player.FindAttachmentBySlotName( "Body" );
        if ( itemClothing ) 
        {
            // 15% de chance de trocar a camisa padrão por uma de time (0.15)
            float chanceCamisa = Math.RandomFloatInclusive(0.0, 1.0);
            if (chanceCamisa <= 0.15)
            {
                GetGame().ObjectDelete(itemClothing); // Remove a camisa padrão
                
                string camisasTime[] = {"Noronha_Tshirt_Palmeiras", "Noronha_Tshirt_Corinthians", "Noronha_Tshirt_Flamengo"};
                int rndCamisa = Math.RandomInt(0, 3);
                
                // Cria e veste a camisa sorteada
                itemClothing = player.GetInventory().CreateAttachment(camisasTime[rndCamisa]);
            }
            SetRandomHealth( itemClothing ); // Aplica o dano aleatório na camisa (nova ou padrão)
        }

        itemClothing = player.FindAttachmentBySlotName( "Legs" );
        if ( itemClothing ) SetRandomHealth( itemClothing );

        itemClothing = player.FindAttachmentBySlotName( "Feet" );
        if ( itemClothing ) SetRandomHealth( itemClothing );

        // --- 2. KIT DE SOBREVIVÊNCIA INICIAL ---
        
        // Curativos (4 Rags) - Atalho 2
        ItemBase rags = ItemBase.Cast(player.GetInventory().CreateInInventory("Rag"));
        if (rags) 
        {
            rags.SetQuantity(4);
            player.SetQuickBarEntityShortcut(rags, 2);
        }
        
        // Luz inicial aleatória - Atalho 1
        string chemlightArray[] = { "Chemlight_White", "Chemlight_Yellow", "Chemlight_Green", "Chemlight_Red" };
        int rndChem = Math.RandomInt( 0, 4 );
        itemEnt = player.GetInventory().CreateInInventory( chemlightArray[rndChem] );
        if (itemEnt)
        {
            SetRandomHealth( itemEnt );
            player.SetQuickBarEntityShortcut(itemEnt, 1);
        }

        // Comida de Praia Aleatória - Atalho 3
        string foodArray[] = { "TunaCan", "SardinesCan", "Noronha_Guarana" };
        int rndFood = Math.RandomInt( 0, 3 );
        itemEnt = player.GetInventory().CreateInInventory( foodArray[rndFood] );
        if (itemEnt)
        {
            SetRandomHealth( itemEnt );
            player.SetQuickBarEntityShortcut(itemEnt, 3);
        }

        // Ferramenta Básica (Faca de Pedra) - Atalho 4
        ItemBase knife = ItemBase.Cast(player.GetInventory().CreateInInventory("StoneKnife"));
        if (knife)
        {
            SetRandomHealth( knife );
            player.SetQuickBarEntityShortcut(knife, 4);
        }
    }
};

// This mission is launched locally with -mission. There is no network client
// connection in that mode, so MissionServer.CreateCharacter is never invoked.
// Create and select the local player explicitly once the MissionGameplay world
// has initialized.
class NoronhaOfflineMission : MissionGameplay
{
    override void OnInit()
    {
        super.OnInit();

        vector spawnPos = "7500 0 7500";
        spawnPos[1] = GetGame().SurfaceY(spawnPos[0], spawnPos[2]);

        PlayerBase player = PlayerBase.Cast(
            GetGame().CreatePlayer(NULL, GetGame().CreateRandomPlayer(), spawnPos, 0, "NONE") );

        if (player)
        {
            GetGame().SelectPlayer(NULL, player);
            Print("[NoronhaOffline] Local player created and selected at " + spawnPos);
        }
        else
        {
            Print("[NoronhaOffline] ERROR: local player creation failed.");
        }
    }
}

Mission CreateCustomMission(string path)
{
    return new NoronhaOfflineMission();
}
