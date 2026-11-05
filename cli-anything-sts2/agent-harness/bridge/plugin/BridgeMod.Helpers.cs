using System;
using System.Collections.Generic;
using System.Net;
using System.Text;
using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Bridge;

public static partial class BridgeMod
{
    private static string? SafeGetCardDescription(CardModel card, PileType pile = PileType.Hand)
    {
        try { return StripRichTextTags(card.GetDescriptionForPile(pile)).Replace("\n", " "); }
        catch { return SafeGetText(() => card.Description)?.Replace("\n", " "); }
    }

    /// <summary>
    /// The state a relic reports about itself (Normal, Active, Disabled), by name. Relics that work once per fight
    /// (Vambrace, Unsettling Lamp) or once per run (Lizard Tail) show whether they are spent through it.
    /// Read by reflection because the property is not part of the surface this mod is built against.
    /// </summary>
    internal static string? RelicStatusName(object relic)
    {
        try
        {
            for (var type = relic.GetType(); type != null; type = type.BaseType)
            {
                var property = type.GetProperty("Status",
                    System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public |
                    System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.DeclaredOnly);
                if (property != null)
                    return property.GetValue(relic)?.ToString();
            }
        }
        catch { }
        return null;
    }

    /// <summary>
    /// Which card types Rainbow Ring has seen this turn, as bits: 1 Attack, 2 Skill, 4 Power. The relic keeps the counts
    /// in private fields and its status only shows that it has already paid out, so without this a state read in the
    /// middle of a turn cannot tell how close it is. Null for any other relic (or if the fields are not there).
    /// </summary>
    internal static int? RelicTypesPlayed(object relic)
    {
        try
        {
            if (relic.GetType().Name != "RainbowRing") return null;
            const System.Reflection.BindingFlags flags = System.Reflection.BindingFlags.Instance |
                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic;
            int Count(string field)
            {
                var info = relic.GetType().GetField(field, flags);
                return info?.GetValue(relic) is int n ? n : throw new MissingFieldException(field);
            }
            return (Count("_attacksPlayedThisTurn") > 0 ? 1 : 0) |
                   (Count("_skillsPlayedThisTurn") > 0 ? 2 : 0) |
                   (Count("_powersPlayedThisTurn") > 0 ? 4 : 0);
        }
        catch { return null; }
    }

    /// <summary>
    /// Whether a once-per-fight relic has already done its job, for the relics whose Status never says so: Permafrost
    /// (block on the first Power) and Ruined Helmet (the one doubled Strength). Null for any other relic.
    /// </summary>
    internal static bool? RelicSpent(object relic)
    {
        try
        {
            string? field = relic.GetType().Name switch
            {
                "Permafrost" => "_activatedThisCombat",
                "RuinedHelmet" => "_usedThisCombat",
                "CentennialPuzzle" => "_usedThisCombat",
                "DemonTongue" => "_triggeredThisTurn",
                _ => null
            };
            if (field == null) return null;
            var info = relic.GetType().GetField(field,
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public |
                System.Reflection.BindingFlags.NonPublic);
            return info?.GetValue(relic) as bool?;
        }
        catch { return null; }
    }

    /// <summary>Adds the extra, relic-specific fields to a relic's entry in the state.</summary>
    internal static void AddRelicExtras(Dictionary<string, object?> entry, object relic)
    {
        var types = RelicTypesPlayed(relic);
        if (types != null) entry["types_played"] = types;
        var spent = RelicSpent(relic);
        if (spent != null) entry["spent"] = spent;
    }

    internal static string? SafeGetText(Func<object?> getter)
    {
        try
        {
            var result = getter();
            if (result == null) return null;
            // If it's a LocString, call GetFormattedText
            if (result is MegaCrit.Sts2.Core.Localization.LocString locString)
                return StripRichTextTags(locString.GetFormattedText());
            return result.ToString();
        }
        catch { return null; }
    }

    internal static string StripRichTextTags(string text)
    {
        // Remove BBCode-style tags like [color=red], [/color], etc.
        // Special case: [img]res://path/to/file.png[/img] → [file.png]
        var sb = new StringBuilder();
        int i = 0;
        while (i < text.Length)
        {
            if (text[i] == '[')
            {
                // Check for [img]...[/img] pattern
                if (text.AsSpan(i).StartsWith("[img]"))
                {
                    int contentStart = i + 5; // length of "[img]"
                    int closeTag = text.IndexOf("[/img]", contentStart, StringComparison.Ordinal);
                    if (closeTag >= 0)
                    {
                        string path = text[contentStart..closeTag];
                        int lastSlash = path.LastIndexOf('/');
                        string filename = lastSlash >= 0 ? path[(lastSlash + 1)..] : path;
                        sb.Append('[').Append(filename).Append(']');
                        i = closeTag + 6; // length of "[/img]"
                        continue;
                    }
                }

                int end = text.IndexOf(']', i);
                if (end >= 0) { i = end + 1; continue; }
            }
            sb.Append(text[i]);
            i++;
        }
        return sb.ToString();
    }

    internal static void SendJson(HttpListenerResponse response, object data)
    {
        string json = JsonSerializer.Serialize(data, _jsonOptions);
        byte[] buffer = Encoding.UTF8.GetBytes(json);
        response.ContentType = "application/json; charset=utf-8";
        response.ContentLength64 = buffer.Length;
        response.OutputStream.Write(buffer, 0, buffer.Length);
        response.Close();
    }

    internal static void SendText(HttpListenerResponse response, string text, string contentType = "text/plain")
    {
        byte[] buffer = Encoding.UTF8.GetBytes(text);
        response.ContentType = $"{contentType}; charset=utf-8";
        response.ContentLength64 = buffer.Length;
        response.OutputStream.Write(buffer, 0, buffer.Length);
        response.Close();
    }

    internal static void SendError(HttpListenerResponse response, int statusCode, string message)
    {
        response.StatusCode = statusCode;
        SendJson(response, new Dictionary<string, object?> { ["error"] = message });
    }

    private static Dictionary<string, object?> Error(string message)
    {
        return new Dictionary<string, object?> { ["status"] = "error", ["error"] = message };
    }

    internal static List<T> FindAll<T>(Node start) where T : Node
    {
        var list = new List<T>();
        if (GodotObject.IsInstanceValid(start))
            FindAllRecursive(start, list);
        return list;
    }

    /// <summary>
    /// FindAll variant that sorts results by visual position (row-major: top-to-bottom, left-to-right).
    /// NGridCardHolder.OnFocus() calls MoveToFront() which scrambles child order for z-rendering.
    /// Sorting by GlobalPosition restores the correct visual order for both single-row (card rewards,
    /// choose-a-card) and multi-row (deck selection grids) layouts.
    /// </summary>
    internal static List<T> FindAllSortedByPosition<T>(Node start) where T : Control
    {
        var list = FindAll<T>(start);
        list.Sort((a, b) =>
        {
            int cmp = a.GlobalPosition.Y.CompareTo(b.GlobalPosition.Y);
            return cmp != 0 ? cmp : a.GlobalPosition.X.CompareTo(b.GlobalPosition.X);
        });
        return list;
    }

    private static void FindAllRecursive<T>(Node node, List<T> found) where T : Node
    {
        if (!GodotObject.IsInstanceValid(node))
            return;
        if (node is T item)
            found.Add(item);
        foreach (var child in node.GetChildren())
            FindAllRecursive(child, found);
    }

    private static List<Dictionary<string, object?>> BuildHoverTips(IEnumerable<IHoverTip> tips)
    {
        var result = new List<Dictionary<string, object?>>();
        try
        {
            var seen = new HashSet<string>();
            foreach (var tip in IHoverTip.RemoveDupes(tips))
            {
                try
                {
                    string? title = null;
                    string? description = null;

                    if (tip is HoverTip ht)
                    {
                        title = ht.Title != null ? StripRichTextTags(ht.Title) : null;
                        description = StripRichTextTags(ht.Description);
                    }
                    else if (tip is CardHoverTip cardTip)
                    {
                        title = SafeGetText(() => cardTip.Card.Title);
                        description = SafeGetCardDescription(cardTip.Card);
                    }

                    if (title == null && description == null) continue;

                    string key = title ?? description!;
                    if (!seen.Add(key)) continue;

                    result.Add(new Dictionary<string, object?>
                    {
                        ["name"] = title,
                        ["description"] = description
                    });
                }
                catch { /* skip individual tip on error */ }
            }
        }
        catch { /* return partial results */ }
        return result;
    }

    internal static T? FindFirst<T>(Node start) where T : Node
    {
        if (!GodotObject.IsInstanceValid(start))
            return null;
        if (start is T result)
            return result;
        foreach (var child in start.GetChildren())
        {
            var val = FindFirst<T>(child);
            if (val != null) return val;
        }
        return null;
    }
}
