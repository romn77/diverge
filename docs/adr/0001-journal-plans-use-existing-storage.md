# Journal plans use the existing journal storage pattern

Trade plans are part of the Journal workflow alongside trade records and trade reviews, so the first version will follow the existing Journal storage pattern: file-backed domain artifacts under the reports journal area, with database metadata used for owner/index scoping when auth/database mode is enabled. We are choosing this over a plan-only database model to avoid splitting one workflow across two persistence styles before the broader Journal storage model is redesigned.
