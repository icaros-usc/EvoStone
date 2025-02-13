﻿using DeckSearch.Search;
using SabberStoneUtil.Config;
using System.IO;
using System;

using Nett;

using SabberStoneUtil.DataProcessing;

namespace DeckSearch
{
    class Program
    {
        static void Main(string[] args)
        {
            // read in config and initialize search space (domain of cards to search)
            var config = Toml.ReadFile<Configuration>(args[0]);
            CardReader.Init(config);

            if(config.Search.Category == "Distributed")
            {
                var search = new DistributedSearch(args[0]);
                search.Run();
            }
            else if(config.Search.Category == "Surrogated")
            {
                var search = new SurrogatedSearch(args[0]);
                search.Run();
            }
        }
    }
}
