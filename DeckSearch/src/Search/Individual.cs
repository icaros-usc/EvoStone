using System;
using System.Linq;
using System.Runtime;
using System.Collections.Generic;

using DeckSearch;

using SabberStoneCore.Model;

// using MapSabber.Messaging;
using SabberStoneUtil;
using SabberStoneUtil.Decks;
using SabberStoneUtil.Messaging;

namespace DeckSearch.Search
{
    public class Individual
    {
        public Individual() { }
        public Individual(Individual other)
        {
            this._cardCounts = other._cardCounts.Select(a => a).ToArray();
            this.Features = other.Features.Select(a => a).ToArray();
            this._cardSet = other._cardSet;
            this.ID = other.ID;
            this.ParentID = other.ParentID;
            this.Fitness = other.Fitness;

            this.OverallData = Utilities.DeepClone<OverallStatistics>(other.OverallData);
            this.StrategyData = Utilities.DeepClone<StrategyStatistics[]>(other.StrategyData);
        }
        private static Random rnd = new Random();
        public static Individual GenerateRandomIndividual(List<Card> cardSet)
        {
            // Generate all card ids and permute them. Use this info to
            // construct counts.
            var available = new List<int>();
            for (int i = 0; i < cardSet.Count; i++)
                for (int cnt = 0; cnt < cardSet[i].MaxAllowedInDeck; cnt++)
                    available.Add(i);

            for (int i = 1; i < available.Count; i++)
            {
                int j = (int)(rnd.NextDouble() * i);
                int tmp = available[i];
                available[i] = available[j];
                available[j] = tmp;
            }

            var cardCounts = new int[cardSet.Count];
            for (int i = 0; i < 30; i++)
            {
                int cardId = available[i];
                cardCounts[cardId]++;
            }

            return new Individual(cardCounts, cardSet);
        }

        private int[] _cardCounts;
        private List<Card> _cardSet;

        public int ID { get; set; }
        public int ParentID { get; set; }

        public OverallStatistics OverallData { get; set; }
        public StrategyStatistics[] StrategyData { get; set; }

        public double Fitness { get; set; }
        public double[] Features { get; set; }
        public string CardRemoved; // used by remove card analysis

        public Individual(int[] cardCounts, List<Card> cardSet)
        {
            _cardCounts = cardCounts;
            _cardSet = cardSet;
            ParentID = -1;
        }

        public Individual(List<string> deck, List<Card> cardSet)
        {
            _cardSet = cardSet;
            ParentID = -1;
            _cardCounts = new int[cardSet.Count];
            foreach (var cardName in deck)
            {
                int idx = cardSet.FindIndex(c => c.Name == cardName);
                _cardCounts[idx]++;
            }
        }

        public double GetStatByName(string name)
        {
            return OverallData.GetStatByName(name);
        }

        // Generate a random individual via mutation
        public Individual Mutate()
        {
            int cardsInDeck = 30;
            var cardCounts = new int[_cardCounts.Length];
            Array.Copy(_cardCounts, cardCounts, cardCounts.Length);

            // Try swapping out cards in a cascading fashion.
            double taken = 0.0;
            while (taken < 0.5 && cardsInDeck > 0)
            {
                int cardNum = rnd.Next(cardsInDeck);

                // Find the cardNum'th card in the set.
                int cardId = 0;
                while (cardCounts[cardId] == 0 || cardNum - cardCounts[cardId] > 0)
                {
                    cardNum -= cardCounts[cardId];
                    cardId++;
                }

                // Remove this card
                cardCounts[cardId]--;
                cardsInDeck--;

                // Keep going?
                taken = rnd.NextDouble();
            }

            // Try putting cards back in until we have a full deck.
            while (cardsInDeck < 30)
            {
                int numTypesAvailable = 0;
                for (int i = 0; i < cardCounts.Length; i++)
                    if (cardCounts[i] < _cardSet[i].MaxAllowedInDeck)
                        numTypesAvailable++;

                // Find a random legal card.
                int typeSelected = rnd.Next(numTypesAvailable);
                int cardId = 0;
                while (cardCounts[cardId] == _cardSet[cardId].MaxAllowedInDeck ||
                       typeSelected > 0)
                {
                    if (cardCounts[cardId] < _cardSet[cardId].MaxAllowedInDeck)
                        typeSelected--;
                    cardId++;
                }

                // Add the card
                cardCounts[cardId]++;
                cardsInDeck++;
            }

            var result = new Individual(cardCounts, _cardSet);
            result.ParentID = ID;
            return result;
        }

        public string[] GetCards()
        {
            var cardList = new List<string>();
            for (int i = 0; i < _cardCounts.Length; i++)
                for (int cnt = 0; cnt < _cardCounts[i]; cnt++)
                    cardList.Add(_cardSet[i].Name);

            return cardList.ToArray();
        }

        public override string ToString()
        {
            return string.Join("", _cardCounts);
        }

        // for hashing
        public override int GetHashCode()
        {
            return this.ToString().GetHashCode();
        }

        public override bool Equals(Object obj)
        {
            Individual other = obj as Individual;
            return this.ID == other.ID;
        }
    }
}
