package org.polis.languagetool;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Pattern;
import org.languagetool.AnalyzedToken;
import org.languagetool.AnalyzedTokenReadings;
import org.languagetool.JLanguageTool;
import org.languagetool.language.Polish;
import org.languagetool.rules.Rule;
import org.languagetool.rules.RuleMatch;
import org.languagetool.synthesis.SynthesizerTools;
import org.languagetool.synthesis.pl.PolishSynthesizer;
import org.languagetool.tagging.pl.PolishTagger;

/**
 * Local newline-delimited JSON bridge for the pinned Polish LanguageTool engine.
 *
 * <p>The default operation preserves the qualified punctuation-rule protocol.
 * The optional {@code synthesize} operation returns context-free forms from the
 * real upstream Polish tagger and synthesizer for explicit source spans. The
 * process keeps resources warm and never opens a listening socket.</p>
 */
public final class PolisStdioServer {
    private static final String SOFTWARE_NAME = "LanguageTool";
    private static final String POLISH_LANGUAGE = "pl-PL";
    private static final String CHECK_OPERATION = "check";
    private static final String INSPECT_OPERATION = "inspect";
    private static final String SYNTHESIZE_OPERATION = "synthesize";
    private static final String TAGS_RESOURCE = "/pl/polish_tags.txt";
    private static final Locale POLISH_LOCALE = Locale.forLanguageTag("pl-PL");
    private static final Pattern TOKEN_PATTERN = Pattern.compile(
            "[\\p{L}\\p{M}'’.-]+"
    );
    private static final Set<String> SUPPORTED_POS = Set.of("subst", "adj");
    private static final Set<String> ALLOWED_RULE_IDS = Set.of(
            "BRAK_PRZECINKA_KTORY",
            "BRAK_PRZECINKA_SPOJNIK_PROSTY",
            "BRAK_PRZECINKA_ZE",
            "BRAK_PRZECINKA_ZEBY",
            "WOLACZ_BEZ_PRZECINKA"
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
                final Request request = parseRequest(line);
                final ObjectNode response;
                if (SYNTHESIZE_OPERATION.equals(request.operation())) {
                    response = synthesize(request);
                } else {
                    response = check(
                            languageTool,
                            request,
                            INSPECT_OPERATION.equals(request.operation())
                    );
                }
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
        final JsonNode textNode = payload.get("text");
        final JsonNode language = payload.get("language");
        if (textNode == null || !textNode.isTextual()) {
            throw new IllegalArgumentException("text must be a string");
        }
        if (language == null || !language.isTextual()) {
            throw new IllegalArgumentException("language must be a string");
        }
        if (!POLISH_LANGUAGE.equals(language.textValue())) {
            throw new IllegalArgumentException("only pl-PL is supported");
        }
        final JsonNode operationNode = payload.get("operation");
        final String operation = operationNode == null
                ? CHECK_OPERATION
                : operationNode.textValue();
        if (!CHECK_OPERATION.equals(operation)
                && !INSPECT_OPERATION.equals(operation)
                && !SYNTHESIZE_OPERATION.equals(operation)) {
            throw new IllegalArgumentException(
                    "operation must be check, inspect, or synthesize"
            );
        }
        final String text = textNode.textValue();
        if (CHECK_OPERATION.equals(operation) || INSPECT_OPERATION.equals(operation)) {
            return new Request(operation, text, List.of());
        }
        final JsonNode spansNode = payload.get("spans");
        if (spansNode == null || !spansNode.isArray() || spansNode.isEmpty()) {
            throw new IllegalArgumentException("synthesize spans must be a non-empty array");
        }
        if (spansNode.size() > 128) {
            throw new IllegalArgumentException("at most 128 spans are supported");
        }
        final int codePointLength = text.codePointCount(0, text.length());
        final List<Span> spans = new ArrayList<>();
        for (JsonNode spanNode : spansNode) {
            if (!spanNode.isObject()
                    || !spanNode.has("start")
                    || !spanNode.has("end")
                    || !spanNode.get("start").isIntegralNumber()
                    || !spanNode.get("end").isIntegralNumber()) {
                throw new IllegalArgumentException("span start and end must be integers");
            }
            final int start = spanNode.get("start").intValue();
            final int end = spanNode.get("end").intValue();
            if (start < 0 || end <= start || end > codePointLength) {
                throw new IllegalArgumentException("span must satisfy 0 <= start < end <= text length");
            }
            final String surface = substringByCodePoints(text, start, end);
            if (!TOKEN_PATTERN.matcher(surface).matches()) {
                throw new IllegalArgumentException("span must select exactly one word token");
            }
            spans.add(new Span(start, end, surface));
        }
        return new Request(operation, text, List.copyOf(spans));
    }

    private static String substringByCodePoints(
            final String text,
            final int start,
            final int end
    ) {
        final int charStart = text.offsetByCodePoints(0, start);
        final int charEnd = text.offsetByCodePoints(0, end);
        return text.substring(charStart, charEnd);
    }

    private static ObjectNode check(
            final JLanguageTool languageTool,
            final Request request,
            final boolean includeUnqualifiedRules
    ) throws Exception {
        final ObjectNode response = JSON.createObjectNode();
        if (includeUnqualifiedRules) {
            response.put("operation", INSPECT_OPERATION);
        }
        response.putObject("software")
                .put("name", SOFTWARE_NAME)
                .put("version", JLanguageTool.VERSION);
        response.putObject("language")
                .put("name", "Polish")
                .put("code", POLISH_LANGUAGE);
        final ArrayNode matches = response.putArray("matches");
        for (RuleMatch match : languageTool.check(request.text())) {
            final String ruleId = match.getSpecificRuleId();
            if (includeUnqualifiedRules || ALLOWED_RULE_IDS.contains(ruleId)) {
                matches.add(toJson(match, ruleId));
            }
        }
        return response;
    }

    private static ObjectNode synthesize(final Request request) throws Exception {
        final ObjectNode response = JSON.createObjectNode();
        response.put("operation", SYNTHESIZE_OPERATION);
        response.put("language", POLISH_LANGUAGE);
        final ArrayNode results = response.putArray("results");
        for (Span span : request.spans()) {
            results.add(synthesizeSpan(span));
        }
        return response;
    }

    private static ObjectNode synthesizeSpan(final Span span) throws Exception {
        final List<AnalyzedTokenReadings> tagged = MorphologyResources.TAGGER.tag(
                List.of(span.surface())
        );
        final List<AnalyzedToken> analyses = tagged.isEmpty()
                ? List.of()
                : tagged.get(0).getReadings();
        final Map<String, CandidateAccumulator> accumulated = new LinkedHashMap<>();
        boolean hasAnalysis = false;
        boolean hasSupportedAnalysis = false;

        for (AnalyzedToken analysis : analyses) {
            final String lemma = analysis.getLemma();
            final String sourceTag = analysis.getPOSTag();
            if (lemma == null || sourceTag == null) {
                continue;
            }
            hasAnalysis = true;
            final String pos = sourceTag.split(":", 2)[0];
            if (!SUPPORTED_POS.contains(pos)) {
                continue;
            }
            hasSupportedAnalysis = true;
            for (String targetTag : MorphologyResources.TAGS) {
                if (!targetTag.startsWith(pos + ":")) {
                    continue;
                }
                final String[] forms = MorphologyResources.SYNTHESIZER.synthesize(
                        analysis,
                        targetTag
                );
                if (forms == null) {
                    continue;
                }
                for (String rawForm : forms) {
                    if (rawForm == null || rawForm.isBlank()) {
                        continue;
                    }
                    final String form = preserveCapitalization(span.surface(), rawForm);
                    addCandidate(accumulated, lemma, form, featuresFromTag(targetTag));
                }
            }
        }

        if (accumulated.values().stream().noneMatch(
                candidate -> candidate.form().equals(span.surface())
        )) {
            addCandidate(
                    accumulated,
                    null,
                    span.surface(),
                    new TreeSet<>(Set.of("unchanged"))
            );
        }

        final String unsupportedReason;
        final long distinctForms = accumulated.values().stream()
                .map(CandidateAccumulator::form)
                .distinct()
                .count();
        if (!hasAnalysis) {
            unsupportedReason = "no-analysis";
        } else if (!hasSupportedAnalysis) {
            unsupportedReason = "unsupported-pos";
        } else if (distinctForms <= 1) {
            unsupportedReason = "no-alternatives";
        } else {
            unsupportedReason = null;
        }

        final ObjectNode result = JSON.createObjectNode();
        result.put("start", span.start());
        result.put("end", span.end());
        result.put("surface", span.surface());
        if (unsupportedReason == null) {
            result.putNull("unsupported_reason");
        } else {
            result.put("unsupported_reason", unsupportedReason);
        }
        final ArrayNode candidates = result.putArray("candidates");
        accumulated.values().stream()
                .sorted(Comparator.comparing(CandidateAccumulator::form))
                .forEach(candidate -> candidates.add(toJson(span, candidate)));
        return result;
    }

    private static void addCandidate(
            final Map<String, CandidateAccumulator> accumulated,
            final String lemma,
            final String form,
            final TreeSet<String> features
    ) {
        final CandidateAccumulator candidate = accumulated.computeIfAbsent(
                form,
                ignored -> new CandidateAccumulator(new TreeSet<>(), form, new TreeSet<>())
        );
        if (lemma != null) {
            candidate.lemmas().add(lemma);
        }
        candidate.features().addAll(features);
    }

    private static TreeSet<String> featuresFromTag(final String tag) {
        final TreeSet<String> features = new TreeSet<>();
        for (String feature : tag.split(":")) {
            if (!feature.isBlank()) {
                features.add(feature);
            }
        }
        return features;
    }

    private static String preserveCapitalization(
            final String surface,
            final String form
    ) {
        if (surface.equals(surface.toUpperCase(POLISH_LOCALE))) {
            return form.toUpperCase(POLISH_LOCALE);
        }
        if (surface.equals(surface.toLowerCase(POLISH_LOCALE))) {
            return form.toLowerCase(POLISH_LOCALE);
        }
        final int firstCodePoint = form.codePointAt(0);
        final int firstLength = Character.charCount(firstCodePoint);
        return form.substring(0, firstLength).toUpperCase(POLISH_LOCALE)
                + form.substring(firstLength).toLowerCase(POLISH_LOCALE);
    }

    private static ObjectNode toJson(
            final Span span,
            final CandidateAccumulator candidate
    ) {
        final ObjectNode result = JSON.createObjectNode();
        result.put("candidate_id", stableCandidateId(span, candidate));
        result.put("start", span.start());
        result.put("end", span.end());
        final String lemma = unambiguousLemma(candidate);
        if (lemma == null) {
            result.putNull("lemma");
        } else {
            result.put("lemma", lemma);
        }
        result.put("form", candidate.form());
        final ArrayNode features = result.putArray("features");
        candidate.features().forEach(features::add);
        return result;
    }

    private static String stableCandidateId(
            final Span span,
            final CandidateAccumulator candidate
    ) {
        final String lemma = unambiguousLemma(candidate);
        final String signature = span.start()
                + "\u0000" + span.end()
                + "\u0000" + (lemma == null ? "" : lemma)
                + "\u0000" + candidate.form()
                + "\u0000" + String.join("\u0000", candidate.features());
        try {
            final MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return "ltpl:" + HexFormat.of().formatHex(
                    digest.digest(signature.getBytes(StandardCharsets.UTF_8))
            );
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException("SHA-256 is unavailable", error);
        }
    }

    private static String unambiguousLemma(final CandidateAccumulator candidate) {
        return candidate.lemmas().size() == 1 ? candidate.lemmas().first() : null;
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

    private static final class MorphologyResources {
        private static final PolishTagger TAGGER = new PolishTagger();
        private static final PolishSynthesizer SYNTHESIZER = PolishSynthesizer.INSTANCE;
        private static final List<String> TAGS = loadTags();

        private MorphologyResources() {
        }

        private static List<String> loadTags() {
            try (InputStream stream = JLanguageTool.getDataBroker()
                    .getFromResourceDirAsStream(TAGS_RESOURCE)) {
                return List.copyOf(SynthesizerTools.loadWords(stream));
            } catch (Exception error) {
                throw new IllegalStateException("cannot load Polish synthesis tags", error);
            }
        }
    }

    private record Request(String operation, String text, List<Span> spans) {
    }

    private record Span(int start, int end, String surface) {
    }

    private record CandidateAccumulator(
            TreeSet<String> lemmas,
            String form,
            TreeSet<String> features
    ) {
    }
}
