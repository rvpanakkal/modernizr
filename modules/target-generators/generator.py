import argparse
import os
import re

try:
    from jinja2 import Environment, FileSystemLoader
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


def lower_first_filter(s: str) -> str:
    if not s:
        return s
    return s[0].lower() + s[1:]


def render_template(template_path: str, context: dict) -> str:
    with open(template_path, "r", encoding="utf-8") as f:
        template_str = f.read()

    if HAS_JINJA2:
        template_dir = os.path.dirname(template_path)
        template_name = os.path.basename(template_path)
        env = Environment(loader=FileSystemLoader(template_dir))
        env.filters["lower_first"] = lower_first_filter
        template = env.get_template(template_name)
        return template.render(context)

    # Standard library fallback engine
    rendered = template_str
    rendered = rendered.replace("{{ entity_name }}", context.get("entity_name", ""))
    rendered = rendered.replace("{{ component_name }}", context.get("component_name", ""))
    rendered = rendered.replace("{{ service_name }}", context.get("service_name", ""))
    rendered = rendered.replace("{{ domain_name }}", context.get("domain_name", ""))
    rendered = rendered.replace("{{ jira_story_id }}", context.get("jira_story_id", ""))
    rendered = rendered.replace("{{ package_name }}", context.get("package_name", ""))
    rendered = rendered.replace("{{ entity_name | lower }}", context.get("entity_name", "").lower())
    rendered = rendered.replace("{{ component_name | lower }}", context.get("component_name", "").lower())
    rendered = rendered.replace("{{ domain_name | lower }}", context.get("domain_name", "").lower())
    rendered = rendered.replace("{{ service_name | lower_first }}", lower_first_filter(context.get("service_name", "")))
    return rendered


def main():
    parser = argparse.ArgumentParser(description="Target Code Generator rendering Jinja2 templates for Java/Spring Boot & Angular.")
    parser.add_argument("--template", "-t", required=True, help="Path to Jinja2 template file")
    parser.add_argument("--output", "-o", required=True, help="Output destination file path")
    parser.add_argument("--jira-id", required=True, help="Mandatory Jira Story ID (e.g. MOD-101)")
    parser.add_argument("--name", required=True, help="Entity or Component Name")

    args = parser.parse_args()

    context = {
        "jira_story_id": args.jira_id,
        "entity_name": args.name,
        "component_name": args.name,
        "service_name": f"{args.name}Service",
        "domain_name": args.name,
        "package_name": "com.enterprise.modernization",
        "fields": [{"name": "accountNumber", "type": "String"}, {"name": "balance", "type": "BigDecimal"}]
    }

    rendered_code = render_template(args.template, context)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(rendered_code)

    print(f"[Generator] Target code rendered successfully to: {args.output}")


if __name__ == "__main__":
    main()
