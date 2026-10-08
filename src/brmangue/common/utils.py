

# dissmodel/executor/utils.py

# TODO: duplicated across brmangue-dissmodel, disslucc-continuous and
# disslucc-discrete. Should be promoted to dissmodel.executor.utils
# (tracked separately).
def default_output_uri(experiment_id: str, ext: str) -> str:
    """
    Returns an s3:// URI when MinIO is reachable, a local path otherwise.

    Intended for use in ModelExecutor.save() implementations when
    output_path is not provided in the experiment record.

    Parameters
    ----------
    experiment_id : str
        Unique experiment identifier — used as the output directory name.
    ext : str
        File extension without the dot (e.g. 'tif', 'gpkg').

    Returns
    -------
    str
        's3://dissmodel-outputs/experiments/{id}/output.{ext}'
        or './outputs/{id}/output.{ext}' if MinIO is not reachable.
    """
    from dissmodel.io._storage import get_default_client
    try:
        get_default_client()
        return f"s3://dissmodel-outputs/experiments/{experiment_id}/output.{ext}"
    except Exception:
        return f"./outputs/{experiment_id}/output.{ext}"

# Parameter names before 0.5.0 → current names (glossary shared with brmangue-terrame)
RENAMED_PARAMETERS: dict[str, str] = {
    "taxa_elevacao": "sea_level_rise_rate",
    "altura_mare":   "tide_height",
    "acrecao_ativa": "accretion_enabled",
}


def reject_renamed_parameters(parameters: dict) -> None:
    """
    Fail with the new name when a parameter uses a name from before 0.5.0.

    Executors read parameters with ``params.get(name, default)``, so an old
    name in a TOML file or ``--param`` would otherwise be ignored silently
    and the run would use the default value.
    """
    old = sorted(k for k in parameters if k in RENAMED_PARAMETERS)
    if old:
        hints = ", ".join(f"'{k}' → '{RENAMED_PARAMETERS[k]}'" for k in old)
        raise ValueError(
            f"Parameter names changed in brmangue-dissmodel 0.5.0: {hints}. "
            "Update the TOML file or --param arguments."
        )
