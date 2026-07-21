package org.polis.languagetool;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;
import org.languagetool.JLanguageTool;
import org.languagetool.language.Polish;
import org.languagetool.rules.Rule;
import org.languagetool.rules.RuleMatch;

/**
 * Local newline-delimited JSON bridge for the pinned Polish LanguageTool engine.
 *
 * <p>Each input line must contain a JSON object with {@code text} and
 * {@code language} fields. Only the two corpus-qualified punctuation rules are
 * emitted. The process keeps one engine instance warm for repeat requests and
 * never opens a listening socket.</p>
 */
public final class PolisStdioServer {
    private static final String SOFTWARE_NAME = "LanguageTool";
    private static final String POLISH_LANGUAGE = "pl-PL";
    private static final Set<String> ALLOWED_RULE_IDS = Set.of(
            "BRAK_PRZECINKA_ZE",
            "BRAK_PRZECINKA_ZEBY"
    );
    private static final ObjectMapper JSON = new ObjectMapper();

    private PolisStdioServer() {
    }

    public static void main(final String[] args) throws Exception {
        final JLanguageTool languageTool = new JLanguageTool(new Polish());
        try (
                BufferedReader input = new BufferedReader(
                        new InputStreamReader(System.in, StandardCharsets.UTF_8)
                );
                BufferedWriter output = new BufferedWriter(
                        new OutputStreamWriter(System.out, StandardCharsets.UTF_8)
                )
        ) {
            String line;
            while ((line = input.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }
                final ObjectNode response = check(languageTool, parseRequest(line));
                output.write(JSON.writeValueAsString(response));
                output.newLine();
                output.flush();
            }
        }
    }

    private static Request parseRequest(final String line) throws Exception {
        final JsonNode payload = JSON.readTree(line);
        if (!payload.isObject()) {
            throw new IllegalArgumentException("request must be a JSON object");
        }
        final JsonNode text = payload.get("text");
        final JsonNode language = payload.get("language");
        if (text == null || !text.isTextual()) {
            throw new IllegalArgumentException("text must be a string");
        }
        if (language == null || !language.isTextual()) {
            throw new IllegalArgumentException("language must be a string");
        }
        if (!POLISH_LANGUAGE.equals(language.textValue())) {
            throw new IllegalArgumentException("only pl-PL is supported");
        }
        return new Request(text.textValue());
    }

    private static ObjectNode check(
            final JLanguageTool languageTool,
            final Request request
    ) throws Exception {
        final ObjectNode response = JSON.createObjectNode();
        response.putObject("software")
                .put("name", SOFTWARE_NAME)
                .put("version", JLanguageTool.VERSION);
        response.putObject("language")
                .put("name", "Polish")
                .put("code", POLISH_LANGUAGE);
        final ArrayNode matches = response.putArray("matches");
        for (RuleMatch match : languageTool.check(request.text())) {
            final String ruleId = match.getSpecificRuleId();
            if (ALLOWED_RULE_IDS.contains(ruleId)) {
                matches.add(toJson(match, ruleId));
            }
        }
        return response;
    }

    private static ObjectNode toJson(final RuleMatch match, final String ruleId) {
        final Rule rule = match.getRule();
        final ObjectNode result = JSON.createObjectNode();
        result.put("message", match.getMessage());
        result.put("offset", match.getFromPos());
        result.put("length", match.getToPos() - match.getFromPos());
        final ArrayNode replacements = result.putArray("replacements");
        final List<String> suggestions = match.getSuggestedReplacements();
        for (String suggestion : suggestions) {
            replacements.addObject().put("value", suggestion);
        }
        final ObjectNode ruleNode = result.putObject("rule");
        ruleNode.put("id", ruleId);
        ruleNode.put("description", rule.getDescription());
        ruleNode.put("issueType", rule.getLocQualityIssueType().toString());
        if (rule.getCategory() != null) {
            ruleNode.putObject("category")
                    .put("id", rule.getCategory().getId().toString())
                    .put("name", rule.getCategory().getName());
        }
        return result;
    }

    private record Request(String text) {
    }
}
