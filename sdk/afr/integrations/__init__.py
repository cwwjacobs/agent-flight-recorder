"""Framework adapters that map third-party callback systems onto AFR events.

Adapters are import-safe: importing this package (or an adapter module)
never requires the third-party framework. Constructing an adapter does —
each one tells you the exact `pip install` to run if its framework is
missing.

    from afr.integrations.langchain import AFRCallbackHandler
"""
