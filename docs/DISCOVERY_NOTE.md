# Return root-cause intelligence discovery note

**Owner:** Neha, Category Head  
**Prepared:** 1 October 2026  
**Scope note:** This note records the decision for the MVP. The database work preceded this note, so it does not meet the brief's requirement that discovery be signed off before the first code was written.

## Problem and evidence

“When I read the Other box by hand, most of it is about fit, but I can only read a few hundred at a time.” The MVP helps Neha turn return comments into reviewable cause labels and SKU/category signals.

The brief reports a 31% overall return rate and says 44% of returns are labelled “Other.” Neha says the comments she reads are mostly about fit. Vendor size charts differ, and the 410,000 product reviews have not been analysed. Growth reports customer acquisition cost is up 40% year on year and repeat purchase has stayed at 22% for six quarters. Better fit information could help the category team improve product/size decisions and support retention; attribution to acquisition is not defined in the data schema.

The brief does not state Dhaga's rupee cost per return. We will not invent one. The existing measures for this MVP are the 44% “Other” share, the accuracy of labels against human review, the share of comments receiving a usable cause, and SKU/category return metrics.

**Success measure:** On a human-labelled sample of “Other” returns, measure category/subcategory accuracy and review rate; report these beside the client-stated 44% “Other” baseline. For operational value, show category users a ranked SKU view with fit return counts and rate. Establish acceptance thresholds with Neha before using outputs for decisions.

## Ranked shortlist

1. **Return root causes — selected.** Neha owns the issue; 31% return rate, 44% “Other,” fit-dominant comments, vendor-specific size charts, and unused review text provide a clear analysis path. Financial cost per return and the downstream acquisition join remain discovery questions.
2. **COD return-to-origin.** Faizan owns it; the brief reports 26% RTO on COD, ₹120 logistics cost per RTO, and 61% of orders paid COD. Directly measurable cost is strong, but intervention causes and customer/order join details need discovery.
3. **Where-is-my-order support.** Arpita owns it; 58% of roughly 9,000 weekly tickets are WISMO and first response averages nine hours. Repetitive replies suggest an automation opportunity, but customer-facing answers need live order data and a safe failure path.
4. **Catalogue launch delays.** Vivek owns it; sample-to-live takes six to nine days, about 400 new SKUs arrive weekly, and Tuesday drops slip. The time loss is clear, but the brief does not quantify revenue impact or define how to measure recovered demand.

## Biggest assumption and test

The largest assumption is that a consistent, human-reviewable taxonomy can recover useful fit causes from the “Other” text at a rate that changes category decisions. Test it on a stratified sample across vendor and category, have Neha or a delegate label it independently, and compare model labels to adjudicated labels. If fit is not dominant or agreement is poor, revisit the problem choice and taxonomy before expanding the MVP.
