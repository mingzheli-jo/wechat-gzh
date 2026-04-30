import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

type Account = {
  id: string;
  name: string;
  category: string;
  is_active: boolean;
};

export default function Accounts() {
  const { data, isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<Account[]>("/accounts")).data,
  });
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-4">公众号</h1>
      {isLoading && <div>加载中...</div>}
      <ul className="space-y-2">
        {data?.map((a) => (
          <li
            key={a.id}
            className="border rounded p-3 flex justify-between"
          >
            <span>{a.name}</span>
            <span className="text-sm text-slate-500">{a.category}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
