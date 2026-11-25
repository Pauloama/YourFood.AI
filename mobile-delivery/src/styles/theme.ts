import { StyleSheet } from 'react-native';

export const themeStyles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#faf7f2'
  },
  container: {
    padding: 16,
    gap: 14
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#ea4c23',
    borderBottomWidth: 1,
    borderBottomColor: '#d43d16'
  },
  title: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: '700'
  },
  subtitle: {
    color: '#6b625b',
    fontSize: 13
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 15,
    borderWidth: 1,
    borderColor: '#ebe3d8',
    gap: 8
  },
  cardTitle: {
    color: '#1c1917',
    fontSize: 16,
    fontWeight: '700'
  },
  text: {
    color: '#1c1917',
    fontSize: 14
  },
  input: {
    backgroundColor: '#ffffff',
    color: '#1c1917',
    borderWidth: 1.5,
    borderColor: '#ebe3d8',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10
  },
  buttonPrimary: {
    backgroundColor: '#ea4c23',
    borderRadius: 10,
    paddingVertical: 11,
    paddingHorizontal: 14,
    alignItems: 'center'
  },
  buttonSecondary: {
    backgroundColor: '#f4efe8',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#ebe3d8',
    paddingVertical: 9,
    paddingHorizontal: 12,
    alignItems: 'center'
  },
  buttonSuccess: {
    backgroundColor: '#159a6e',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
    alignItems: 'center'
  },
  buttonText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 14
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap'
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8
  },
  badge: {
    backgroundColor: '#fff0eb',
    color: '#ea4c23',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    fontSize: 12,
    fontWeight: '700',
    overflow: 'hidden'
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#ffffff',
    borderTopWidth: 1,
    borderTopColor: '#ebe3d8',
    padding: 8,
    gap: 8
  },
  tabItem: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: '#f4efe8',
    alignItems: 'center'
  },
  tabActive: {
    backgroundColor: '#ea4c23'
  },
  errorText: {
    color: '#991b1b',
    backgroundColor: '#fee2e2',
    padding: 10,
    borderRadius: 10
  }
});
