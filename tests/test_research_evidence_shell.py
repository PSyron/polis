"""Product boundary for the retained, non-executable v2 research evidence."""

# ruff: noqa: E501

from __future__ import annotations

import subprocess
from hashlib import sha256
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RETAINED_EVIDENCE_SHA256 = {
    "experiments/a-b-one-shot/README.md": "64842d74b48a32e6bb7e2274f58877496c65e963165b245cf04d67de78f45266",
    "experiments/a-b-one-shot/config.json": "e6316a6fb2c764e2ccd95dbbfff9c00b37575d9aefe79af0673e4a3f88fbd595",
    "experiments/a-b-one-shot/dataset.manifest.json": "3f80ef44ce11b7e4d492e340c0265ff8913fe766a8a4b98377bc55540e58c6d7",
    "experiments/a-b-one-shot/holdout.started": "b4d6e27aaec54471b25970f6d20ea515893563508806b6a6ddf0ce88bf696dae",
    "experiments/a-b-one-shot/normalized-report.json": "3bf34f54b68d62d84a9d34b6ca0bd1cf878fc30c718d4179791aa6349a94fc58",
    "experiments/a-b-one-shot/preregistration.json": "3eda81de3349453b2a57ffae65d8d9d4db1c389d1e24ea3f6328046922266be8",
    "experiments/a-b-one-shot/report.json": "808b7838179b641ff400c78441b7c9b42d4cac245cded7a391882ae9d29d4365",
    "experiments/a-b-one-shot/result.manifest.json": "9b08fa964efe50224deb2cb5e4a1a76ac7060335d223b2449cc5a29657322578",
    "experiments/contextual_inflection_routing/README.md": "d2a39cb1763f519e4249ca63cd59749975b710425a1def055bf14528d7059964",
    "experiments/contextual_inflection_routing/config.json": "8b5af09fc6cb780067387eb75ce27e2f33bbe4b4f74938a2d323065520ed5d05",
    "experiments/contextual_inflection_routing/frozen_router.json": "73e61539f4373d75b4df65b3ee52b5b73ef6f8b101a7bbfe4ba5da6e5af8f22e",
    "experiments/contextual_inflection_routing/holdout.started": "65761ea7208b58e51d0e46a57388afc15ba9827a7f7e0c148d41553f90776ce4",
    "experiments/contextual_inflection_routing/report.json": "83a31a2faace9493cafb1e1d9d684616a3e94c7e8dca2fc9ca5650c5719f07ba",
    "experiments/inflection_candidates/README.md": "b872846c19506e88b8854309c3a0d50c55dfc0e34942323c652180a4deeb20d0",
    "experiments/inflection_candidates/cases.json": "939a3b9f42274d7307fbe51d9474392ce57cd0cd028fd1a028ab9a56db50380d",
    "experiments/languagetool_rule_inventory/README.md": "0e7dea84cca48ea36239afc1d09351a6f4a7436ad2b50ba01040b28e27fee5cc",
    "experiments/languagetool_rule_inventory/config.json": "3ef2a23ef992ecb6b9171a3f0bd821ef5296d854ba76a5e6006d2d1d09ba0fa1",
    "experiments/languagetool_rule_inventory/frozen_allowlist.json": "276fdd0fb895c7d7d983f545ff30338580805b8a2ec9636fadaaff1845b68e67",
    "experiments/languagetool_rule_inventory/holdout.started": "867fc697eb24bd90cbea716891a841b205574f594b47173b20b2bff8b6fa917d",
    "experiments/languagetool_rule_inventory/report.json": "d3b48165cf004a5a89916d24738b27a32060b91ab611c85d4933378221062ead",
    "experiments/languagetool_spike/README.md": "67af919a8005066ed6893b7b7b3f81f15dce3da701a460f8d0d7649c373e3b38",
    "experiments/languagetool_stdio_session/README.md": "c75d3cc14f21205400be4f184b4508c40c2e0fc487c145146f0c46a202e3699f",
    "experiments/languagetool_stdio_session/config.json": "8af2d99df0fb03a4a9306eab031d7780996dda08261cf754963f4735903e4130",
    "experiments/languagetool_stdio_session/report.json": "da7ba867734c607782df204221080ab70c29f59c18bca7cc31e21960cef07322",
    "experiments/llm_backends/README.md": "4d4fb054e5508158611cd60e55348aa1864acdc2e1e7abe7599bec8deb823afa",
    "experiments/llm_backends/results.json": "80f84987b2246b92cdaad5486986d25848d4fc85298398012ac6acf036dedd41",
    "experiments/nlp_dependencies/README.md": "cb58ab50f907722adbf89139b549d49669079280689a4c462f043039ef214781",
    "experiments/nlp_dependencies/assembly.json": "5081fde58104cd9aea48cee1f82ff88cd0cb23803f90acda2b3a68eb1ad7777f",
    "experiments/nlp_dependencies/cases.json": "2bcc80e31ce8640eef488782662afb9d7e576ee4f35aaf1d3c945469766e011c",
    "experiments/nlp_dependencies/closures/spacy-pl.txt": "6457f1412e8540b43787b155524f9f9aa93b5db6b8896b33d41aefebdf423a0d",
    "experiments/nlp_dependencies/closures/stanza-pl.txt": "efbc2f37c0539745b5a2e3804b0f38d66db63e7d009ae2d7501f574f1fa62cc1",
    "experiments/nlp_dependencies/closures/stdlib-morfeusz2.txt": "343755a5a5c59afa437e3c20377e330ff9c337fe66ff1fb3efc256261e6d6b90",
    "experiments/nlp_dependencies/closures/stdlib.txt": "6e51119a12e39c374ae02e3af020ac60ea6e3cd54cf9f83a585d7782ddd4cca9",
    "experiments/nlp_dependencies/raw/spacy-pl.json": "b404cf4f9ddcb873d971128513964425cea834a282d40c3263970179922797e8",
    "experiments/nlp_dependencies/raw/stanza-pl.json": "f608b2f3d99fd2583fd977aab850c1fa4e05d69e934096677d79663bae6e9f91",
    "experiments/nlp_dependencies/raw/stdlib-morfeusz2.json": "9f3353f21edc36019752fda9f8c80698426eb51f781b034faebe1f84194839a7",
    "experiments/nlp_dependencies/raw/stdlib.json": "eb19cb294003e6f3067aaa358bbec633f8df77ed94c257fd2a1a61a6d58ccce4",
    "experiments/nlp_dependencies/results.json": "b1abb60db61be5e906a92fdb220d50e79b3f56a764944d88879feeb1acd6c819",
    "experiments/qlora_benchmark/README.md": "6000da3e6baed5e136ae037059960e7c0d4a890b19d967f069ab858a830f1ba5",
    "experiments/qlora_benchmark/config.json": "e77d8301af0cecf20bb60c29ede2ce1bc9a4656e205cf7f5c5d9a3bdab857d32",
    "experiments/qlora_benchmark/report.json": "9267bfaf42d5a017eb5386e0ef041b9656443c74c36dc0871da9e75132052df7",
    "experiments/real_llm_benchmark/README.md": "d82116fc12bba5f87d5bfc29ffba33cc754fce70eddc050862bf2fe929f3eb4c",
    "experiments/residual_syntax_rules/README.md": "8897ade7f611e6cb862ece6f1cc0adcbfdd68bb2026a76800c2994d7f93829f7",
    "experiments/residual_syntax_rules/config.json": "6aa1cf64dc54e723cbce79b5985f751782bc312adba1c4236a70b9a74ec6c5e0",
    "experiments/residual_syntax_rules/frozen_rules.json": "72ba1cc2d412cad557725be77d174344e11eb4261a089dd79f3a1ac74f92a025",
    "experiments/residual_syntax_rules/holdout.started": "d598ede85eeb7183b9aa4663c65ab3c38b4128bf0dce33d85ca5f8f130e80c98",
    "experiments/residual_syntax_rules/report.json": "d636b52d6753f672ef408b5dcc8fb1d0d6c3ccc79df4b4097d152f35e2b424f2",
    "experiments/role_prompt_benchmark/README.md": "87f8f757c9cede8eb2020303505f76e3d1040df6184e86cfa15a05dc2954d282",
    "experiments/sentence_category_routing/README.md": "e8224427671917f79f59844c555594fbd444fd51028e2eb11d1e4d3af5a5882b",
    "experiments/sentence_category_routing/config.json": "48f1fb835116d1ed3ad59ba5b6d913090b333ea67ce0378693a0e05121be85f5",
    "experiments/sentence_category_routing/report.json": "7c0ecb4174e84fb68d1cfcc4210bb6207525e992f81af252f58555e7f68f44e3",
    "experiments/sentence_safety_gate/README.md": "e32140dd11b9324e043da4b8bddc6fbe2222ef35327f6c6d37246d52c6afa3ee",
    "experiments/sentence_safety_gate/config.json": "6c637167d7cb77003db28e6072009a2606a45597dfee1ec3173f31c2dea87fc6",
    "experiments/sentence_safety_gate/evaluated_source.json": "b1bd4fda10301c06dbe5fd6c0397f88c1acf44016652299de854a4001acd5ab9",
    "experiments/sentence_safety_gate/frozen_gate.json": "9fe74303924707df59d44a654877cec074219ea6f3314d2a60c993052d8ab736",
    "experiments/sentence_safety_gate/holdout.started": "198371e64acb4fe04c8b2ae962e172b37e61ef3149b2d832c97175bde10f4d82",
    "experiments/sentence_safety_gate/report.json": "69c88ac8370ff9d604a4669b674dc242954c6b28cc7c6e7d60ade6764f8a1c99",
    "experiments/sentence_safety_gate_v2/README.md": "a7bcffa26f8bea0640097bb00784c3a206893f561618742557bea54df9349354",
    "experiments/sentence_safety_gate_v2/config.json": "d4aaf92f2f8f9dc83558108b14de4a8f5a5b196588cb5e7717dc46b89a9d43ff",
    "experiments/sentence_safety_gate_v2/evaluated_source.json": "da2eae4973b0b9d39076b9628eea92de58c689c6924d0ceec1198f16b204e091",
    "experiments/sentence_safety_gate_v2/pre_evaluation_inputs.patch": "32a5419baf4bf673bcfb181b19e5533886e57ee71acc0089770db06969144aa2",
    "experiments/sentence_safety_gate_v2/report.json": "7485c543a5abcfe45096cfc9334b59cf4c5dd510186c6318a44d0c38cdeb1141",
    "experiments/sentence_syntax_qualification/README.md": "9414dc5fda5c29bdac6652c2cbb6d38c0c2801a3549cb7d4cf11cad35b1a3f3c",
    "experiments/sentence_syntax_qualification/config.json": "9858f54577af201f9f4c134fc49e4498f32158dd0b1b2ca724a94957f6dca1f8",
    "experiments/sentence_syntax_qualification/report.json": "fd7f1b250b9fd2fde3e3067000b79a43f7fe15e94643e849bbb216cdc68e2181",
    "experiments/two_pass_qwen35/README.md": "13556ea976902269e8492143ab6eaafce1252ec7562731dcfea2ace68401728e",
    "experiments/two_pass_qwen35/config.json": "4fa3f3d5fe24c9c4bcfb4163baa860f6b4ec9a31a3d9fc694175e863967d6b1b",
    "experiments/two_pass_qwen35/report.json": "8b93335b85e1952b50c2545bb244bc73e2ea3bf3107fb5c9830bda5658970b7b",
}


def _tracked_paths(pathspec: str) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", pathspec],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(
        sorted(path.decode("utf-8") for path in result.stdout.split(b"\0") if path)
    )


def test_experiments_are_an_immutable_non_executable_evidence_shell() -> None:
    assert _tracked_paths("experiments/**/*.py") == ()

    retained_paths = _tracked_paths("experiments/**")
    retained_evidence_paths = tuple(
        path for path in retained_paths if not path.endswith(".py")
    )
    assert retained_evidence_paths == tuple(RETAINED_EVIDENCE_SHA256)

    actual_sha256 = {
        path: sha256((REPOSITORY_ROOT / path).read_bytes()).hexdigest()
        for path in retained_evidence_paths
    }
    assert actual_sha256 == RETAINED_EVIDENCE_SHA256
